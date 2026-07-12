"""Run host shell commands as the low-privilege Rasputin_sbx sandbox account.

Phase 3 / Step 3. This module is Windows-only in effect; it imports cleanly on
every platform (all Win32/ctypes work is lazy, inside functions) so the rest of
the backend and the test suite don't need to care.

What lives here today (the verifiable, account-independent foundation):
  - reading + guarding the sandbox credential written by scripts/Provision-Sandbox.ps1
    (SID-ownership check + DPAPI-CurrentUser decrypt), and
  - `sandbox_provisioned()` used to gate shell routing and auto-provisioning.

`run_as_sandbox()` (the CreateProcessWithLogonW + Job Object + pipe-pump executor)
is intentionally a stub until the account exists on a dev box — its logon/job
behavior can only be written and verified against a real Rasputin_sbx, so building
it blind would risk rework (see docs/EXECUTION_PLAN.md, Step 3 design review).
"""
import base64
import json
import os
import subprocess
import threading
from pathlib import Path

from backend.core.datadir import data_dir

_WINDOWS = os.name == "nt"
CRED_FILENAME = "sandbox.cred"
DEFAULT_ACCOUNT = "Rasputin_sbx"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROVISION_SCRIPT = _REPO_ROOT / "scripts" / "Provision-Sandbox.ps1"


class SandboxError(Exception):
    """Base for sandbox provisioning/execution problems."""


class SandboxNotProvisioned(SandboxError):
    """No usable sandbox credential is present (missing, unreadable, or for another user)."""


class SandboxCredentialMismatch(SandboxNotProvisioned):
    """The credential was created by a different Windows user and cannot be decrypted here."""


def _cred_path(cred_path=None):
    return Path(cred_path) if cred_path is not None else (data_dir() / CRED_FILENAME)


# --------------------------------------------------------------------------- #
# Win32 helpers (lazy — only touched on Windows)
# --------------------------------------------------------------------------- #
def _current_user_sid():
    """Return the current process user's SID as a string (e.g. 'S-1-5-21-...')."""
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

    TOKEN_QUERY = 0x0008
    TokenUser = 1

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise OSError(ctypes.get_last_error(), "OpenProcessToken failed")
    try:
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(token, TokenUser, None, 0, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, TokenUser, buf, size, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation failed")
        # TOKEN_USER begins with SID_AND_ATTRIBUTES whose first field is the PSID pointer.
        sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        str_sid = ctypes.c_wchar_p()
        if not advapi32.ConvertSidToStringSidW(sid_ptr, ctypes.byref(str_sid)):
            raise OSError(ctypes.get_last_error(), "ConvertSidToStringSidW failed")
        try:
            return str_sid.value
        finally:
            kernel32.LocalFree(str_sid)
    finally:
        kernel32.CloseHandle(token)


def _dpapi_unprotect(blob):
    """Decrypt a DPAPI blob for the current user (mirrors ProtectedData.Protect CurrentUser)."""
    import ctypes
    from ctypes import wintypes

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(ctypes.c_wchar_p), ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    buf_in = ctypes.create_string_buffer(bytes(blob), len(blob))
    blob_in = DATA_BLOB(len(blob), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
    ):
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed (credential is for another user or corrupt)")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


# --------------------------------------------------------------------------- #
# Credential loading + guard
# --------------------------------------------------------------------------- #
def load_sandbox_credential(cred_path=None):
    """Return (account_name, password) from the provisioned credential, or raise.

    Guards, in order:
      - file must exist and parse            -> SandboxNotProvisioned
      - recorded ownerSid must match this    -> SandboxCredentialMismatch
        Windows user (clear error for the
        standard-user auto-provision case)
      - DPAPI blob must decrypt for this user-> SandboxCredentialMismatch
    The password is returned to the caller, which must use it immediately and not
    persist it. It is never logged here.
    """
    if not _WINDOWS:
        raise SandboxNotProvisioned("the sandbox account is a Windows-only mechanism")

    path = _cred_path(cred_path)
    if not path.exists():
        raise SandboxNotProvisioned(f"no sandbox credential at {path} — run scripts/Provision-Sandbox.ps1")
    try:
        # utf-8-sig tolerates the BOM that PowerShell 5.1's Set-Content -Encoding UTF8
        # prepends (the provision script writes this file), and reads clean UTF-8 too.
        record = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SandboxNotProvisioned(f"sandbox credential at {path} is unreadable: {exc}") from exc

    account = record.get("account")
    owner_sid = record.get("ownerSid")
    dpapi_b64 = record.get("dpapi")
    if not (account and owner_sid and dpapi_b64):
        raise SandboxNotProvisioned("sandbox credential is missing required fields — re-provision")

    current_sid = _current_user_sid()
    if owner_sid != current_sid:
        raise SandboxCredentialMismatch(
            "sandbox credential belongs to a different Windows user "
            f"({owner_sid} vs current {current_sid}) — re-provision as the account that runs Rasputin"
        )

    try:
        password_bytes = _dpapi_unprotect(base64.b64decode(dpapi_b64))
    except OSError as exc:
        # Backstop: even if the SID check passed, a cross-user or corrupt blob fails here.
        raise SandboxCredentialMismatch(str(exc)) from exc

    return account, password_bytes.decode("utf-8")


def sandbox_provisioned(cred_path=None):
    """True iff a usable sandbox credential exists and decrypts for the current user.

    Account existence itself is enforced at exec time (CreateProcessWithLogonW fails
    closed if the account was removed); this gate is about the credential.
    """
    if not _WINDOWS:
        return False
    try:
        load_sandbox_credential(cred_path)
        return True
    except SandboxNotProvisioned:
        return False


def sandbox_account_name(cred_path=None):
    """The provisioned account name (read without decrypting), or None."""
    try:
        record = json.loads(_cred_path(cred_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return record.get("account")


def ensure_provisioned(timeout=180):
    """Make sure the sandbox account exists, raising ONE UAC prompt to run the
    provision script if it doesn't. Returns True iff provisioned afterward.

    Windows-only; blocking — call via asyncio.to_thread. `Start-Process -Verb RunAs`
    elevates the SAME user, so the DPAPI-CurrentUser credential stays decryptable by
    this (unelevated) backend. Declining the prompt (or a standard-user cross-account
    elevation, caught by the ownerSid guard) leaves it unprovisioned and returns False;
    the caller must then fail closed and NOT enable Host Shell.
    """
    if not _WINDOWS:
        return False
    if sandbox_provisioned():
        return True
    if not _PROVISION_SCRIPT.exists():
        return False
    inner = (
        "Start-Process -Verb RunAs -Wait -FilePath 'powershell' -ArgumentList "
        "'-NoProfile','-ExecutionPolicy','Bypass','-File','{}'".format(_PROVISION_SCRIPT)
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", inner],
                       timeout=timeout, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # declined UAC throws; fall through to the authoritative re-check
    return sandbox_provisioned()


# --------------------------------------------------------------------------- #
# Workspace ACL — the one hole we open for the sandbox account (no elevation:
# a folder's owner can rewrite its DACL). Grant on Host Shell enable so the
# account can reach the workspace; revoke on disable so it can't.
# --------------------------------------------------------------------------- #
def grant_workspace_acl(path):
    """Grant the sandbox account inherited Modify on a workspace tree. No-op
    unless Windows + provisioned. Returns True if the grant was attempted."""
    if not (_WINDOWS and sandbox_provisioned()):
        return False
    account = sandbox_account_name()
    if not account:
        return False
    try:
        subprocess.run(["icacls", str(path), "/grant", f"{account}:(OI)(CI)M"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        return True
    except Exception:
        return False


def revoke_workspace_acl(path):
    """Remove the sandbox account's ACE from a workspace tree. No-op off Windows."""
    if not _WINDOWS:
        return False
    account = sandbox_account_name() or DEFAULT_ACCOUNT
    try:
        subprocess.run(["icacls", str(path), "/remove", account],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Executor — run a command AS the sandbox account (Windows-only machinery)
# --------------------------------------------------------------------------- #
if _WINDOWS:
    import ctypes as _ct
    from ctypes import wintypes as _wt

    _kernel32 = _ct.WinDLL("kernel32", use_last_error=True)
    _advapi32 = _ct.WinDLL("advapi32", use_last_error=True)

    _STARTF_USESTDHANDLES = 0x00000100
    _CREATE_NO_WINDOW = 0x08000000
    _CREATE_SUSPENDED = 0x00000004
    _CREATE_NEW_PROCESS_GROUP = 0x00000200
    _LOGON_WITH_PROFILE = 0x00000001
    _HANDLE_FLAG_INHERIT = 0x00000001
    _WAIT_TIMEOUT = 0x00000102
    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    class _SECURITY_ATTRIBUTES(_ct.Structure):
        _fields_ = [("nLength", _wt.DWORD), ("lpSecurityDescriptor", _wt.LPVOID), ("bInheritHandle", _wt.BOOL)]

    class _STARTUPINFO(_ct.Structure):
        _fields_ = [
            ("cb", _wt.DWORD), ("lpReserved", _wt.LPWSTR), ("lpDesktop", _wt.LPWSTR),
            ("lpTitle", _wt.LPWSTR), ("dwX", _wt.DWORD), ("dwY", _wt.DWORD), ("dwXSize", _wt.DWORD),
            ("dwYSize", _wt.DWORD), ("dwXCountChars", _wt.DWORD), ("dwYCountChars", _wt.DWORD),
            ("dwFillAttribute", _wt.DWORD), ("dwFlags", _wt.DWORD), ("wShowWindow", _wt.WORD),
            ("cbReserved2", _wt.WORD), ("lpReserved2", _ct.POINTER(_ct.c_byte)),
            ("hStdInput", _wt.HANDLE), ("hStdOutput", _wt.HANDLE), ("hStdError", _wt.HANDLE),
        ]

    class _PROCESS_INFORMATION(_ct.Structure):
        _fields_ = [("hProcess", _wt.HANDLE), ("hThread", _wt.HANDLE),
                    ("dwProcessId", _wt.DWORD), ("dwThreadId", _wt.DWORD)]

    class _IO_COUNTERS(_ct.Structure):
        _fields_ = [(n, _ct.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(_ct.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", _ct.c_longlong), ("PerJobUserTimeLimit", _ct.c_longlong),
            ("LimitFlags", _wt.DWORD), ("MinimumWorkingSetSize", _ct.c_size_t),
            ("MaximumWorkingSetSize", _ct.c_size_t), ("ActiveProcessLimit", _wt.DWORD),
            ("Affinity", _ct.c_size_t), ("PriorityClass", _wt.DWORD), ("SchedulingClass", _wt.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(_ct.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", _ct.c_size_t), ("JobMemoryLimit", _ct.c_size_t),
            ("PeakProcessMemoryUsed", _ct.c_size_t), ("PeakJobMemoryUsed", _ct.c_size_t),
        ]

    _advapi32.CreateProcessWithLogonW.argtypes = [
        _wt.LPCWSTR, _wt.LPCWSTR, _wt.LPCWSTR, _wt.DWORD, _wt.LPCWSTR, _wt.LPWSTR, _wt.DWORD,
        _wt.LPVOID, _wt.LPCWSTR, _ct.POINTER(_STARTUPINFO), _ct.POINTER(_PROCESS_INFORMATION)]
    _advapi32.CreateProcessWithLogonW.restype = _wt.BOOL
    _kernel32.CreatePipe.argtypes = [
        _ct.POINTER(_wt.HANDLE), _ct.POINTER(_wt.HANDLE), _ct.POINTER(_SECURITY_ATTRIBUTES), _wt.DWORD]
    _kernel32.ReadFile.argtypes = [_wt.HANDLE, _wt.LPVOID, _wt.DWORD, _ct.POINTER(_wt.DWORD), _wt.LPVOID]
    _kernel32.ReadFile.restype = _wt.BOOL
    _kernel32.CreateJobObjectW.argtypes = [_wt.LPVOID, _wt.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = _wt.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [_wt.HANDLE, _ct.c_int, _wt.LPVOID, _wt.DWORD]
    _kernel32.AssignProcessToJobObject.argtypes = [_wt.HANDLE, _wt.HANDLE]
    _kernel32.TerminateJobObject.argtypes = [_wt.HANDLE, _wt.UINT]
    _kernel32.ResumeThread.argtypes = [_wt.HANDLE]
    _kernel32.WaitForSingleObject.argtypes = [_wt.HANDLE, _wt.DWORD]
    _kernel32.GetExitCodeProcess.argtypes = [_wt.HANDLE, _ct.POINTER(_wt.DWORD)]

    def _make_pipe():
        sa = _SECURITY_ATTRIBUTES()
        sa.nLength = _ct.sizeof(sa)
        sa.bInheritHandle = True
        read, write = _wt.HANDLE(), _wt.HANDLE()
        if not _kernel32.CreatePipe(_ct.byref(read), _ct.byref(write), _ct.byref(sa), 0):
            raise _ct.WinError(_ct.get_last_error())
        _kernel32.SetHandleInformation(read, _HANDLE_FLAG_INHERIT, 0)  # our read end stays private
        return read, write

    def _drain(handle, sink, state):
        buf = _ct.create_string_buffer(8192)
        n = _wt.DWORD(0)
        while _kernel32.ReadFile(handle, buf, 8192, _ct.byref(n), None) and n.value:
            chunk = buf.raw[:n.value]
            with state["lock"]:
                if state["total"] < state["cap"]:
                    take = min(len(chunk), state["cap"] - state["total"])
                    sink.append(chunk[:take])
                    state["total"] += take
                    if take < len(chunk):
                        state["truncated"] = True
                else:
                    state["truncated"] = True  # keep draining so the child never blocks

    def _taskkill_tree(pid):
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            pass


def run_as_sandbox(command_line, cwd, timeout, max_output_chars=20000):
    """Run `command_line` AS the sandbox account; return a shell_exec-shaped dict.

    Blocking (call via asyncio.to_thread). WaitForSingleObject is the SOLE finite
    timeout for this path — do not wrap it in an outer asyncio timeout, since a
    to_thread call can't be cancelled. Tree-kill on timeout is `taskkill /F /T`
    (PRIMARY — the seclogon-created process may escape our Job Object, §9-T5); the
    Job Object's KILL_ON_JOB_CLOSE is defense-in-depth. Env is NULL so the account
    gets its own profile (LOGON_WITH_PROFILE) rather than the operator's PATH.
    """
    if not _WINDOWS:
        raise SandboxNotProvisioned("run_as_sandbox is a Windows-only mechanism")
    account, password = load_sandbox_credential()  # raises SandboxNotProvisioned/Mismatch

    out_r, out_w = _make_pipe()
    err_r, err_w = _make_pipe()
    si = _STARTUPINFO()
    si.cb = _ct.sizeof(si)
    si.dwFlags = _STARTF_USESTDHANDLES
    si.hStdOutput, si.hStdError, si.hStdInput = out_w, err_w, None
    pi = _PROCESS_INFORMATION()
    cmd_buf = _ct.create_unicode_buffer(command_line)

    created = _advapi32.CreateProcessWithLogonW(
        account, ".", password, _LOGON_WITH_PROFILE, None, cmd_buf,
        _CREATE_SUSPENDED | _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP,
        None, cwd, _ct.byref(si), _ct.byref(pi))
    password = None  # drop the secret reference as early as possible
    if not created:
        winerr = _ct.get_last_error()
        for handle in (out_r, out_w, err_r, err_w):
            _kernel32.CloseHandle(handle)
        raise SandboxError(
            f"CreateProcessWithLogonW failed (WinError {winerr}) — the sandbox account may be "
            "removed or disabled; re-run scripts/Provision-Sandbox.ps1")

    # Defense-in-depth Job Object (taskkill is the primary kill; this catches strays).
    job = _kernel32.CreateJobObjectW(None, None)
    if job:
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        _kernel32.SetInformationJobObject(
            job, _JobObjectExtendedLimitInformation, _ct.byref(info), _ct.sizeof(info))
        _kernel32.AssignProcessToJobObject(job, pi.hProcess)  # may no-op via seclogon (§9-T5)

    _kernel32.CloseHandle(out_w)  # parent must drop write ends so ReadFile sees EOF
    _kernel32.CloseHandle(err_w)

    state = {"total": 0, "truncated": False, "cap": max_output_chars, "lock": threading.Lock()}
    out_chunks, err_chunks = [], []
    threads = [
        threading.Thread(target=_drain, args=(out_r, out_chunks, state)),
        threading.Thread(target=_drain, args=(err_r, err_chunks, state)),
    ]
    for thread in threads:
        thread.start()

    _kernel32.ResumeThread(pi.hThread)  # start-draining-then-resume (avoids buffer deadlock)
    waited = _kernel32.WaitForSingleObject(pi.hProcess, max(1, int(timeout)) * 1000)
    timed_out = waited == _WAIT_TIMEOUT
    if timed_out:
        _taskkill_tree(pi.dwProcessId)              # PRIMARY tree kill
        if job:
            _kernel32.TerminateJobObject(job, 1)    # backup
        _kernel32.WaitForSingleObject(pi.hProcess, 5000)

    for thread in threads:
        thread.join(timeout=5)

    code = _wt.DWORD()
    _kernel32.GetExitCodeProcess(pi.hProcess, _ct.byref(code))
    exit_code = None if timed_out else code.value

    for handle in (out_r, err_r, pi.hProcess, pi.hThread):
        _kernel32.CloseHandle(handle)
    if job:
        _kernel32.CloseHandle(job)  # closing the job kills any stragglers (KILL_ON_JOB_CLOSE)

    stdout = b"".join(out_chunks).decode("utf-8", "replace")
    stderr = b"".join(err_chunks).decode("utf-8", "replace")
    output = stdout if not stderr else (stdout + ("\n" if stdout else "") + stderr)
    if state["truncated"]:
        output += f"\n[output truncated at {max_output_chars} chars]"
    return {"exit_code": exit_code, "timed_out": timed_out, "output": output, "truncated": state["truncated"]}
