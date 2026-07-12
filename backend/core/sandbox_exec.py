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
from pathlib import Path

from backend.core.datadir import data_dir

_WINDOWS = os.name == "nt"
CRED_FILENAME = "sandbox.cred"


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


# --------------------------------------------------------------------------- #
# Executor — DEFERRED until a real Rasputin_sbx exists (see module docstring)
# --------------------------------------------------------------------------- #
async def run_as_sandbox(command_line, cwd, timeout, shell=None):
    """Run a command as the sandbox account and return the shell_exec result dict.

    NOT YET IMPLEMENTED. Will use CreateProcessWithLogonW (ctypes/advapi32) with
    CREATE_SUSPENDED|CREATE_NO_WINDOW|CREATE_NEW_PROCESS_GROUP and NULL env
    (LOGON_WITH_PROFILE gives the account its own profile env), hand-rolled pipes
    (POC-proven), a Job Object with KILL_ON_JOB_CLOSE as defense-in-depth, and
    Stage 3.1's taskkill /F /T as the PRIMARY timeout tree-kill (the job assignment
    can be no-op'd by the seclogon service, §9-T5). The whole blocking dance runs
    via asyncio.to_thread with WaitForSingleObject as the sole finite timeout.
    Built and verified against a real account after the one provisioning run.
    """
    raise NotImplementedError(
        "run_as_sandbox is not implemented yet — provision the sandbox account first "
        "(scripts/Provision-Sandbox.ps1), then this executor lands (EXECUTION_PLAN.md Step 3)."
    )
