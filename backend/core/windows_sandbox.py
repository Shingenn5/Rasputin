"""Development-only Windows AppContainer execution probe.

Not registered as an agent tool or an execution authorization. Production shell and
validation remain disabled. Only disposable fixture files belong in this runner.
"""
from __future__ import annotations

import ctypes as C
from contextlib import contextmanager
from ctypes import wintypes as W
import os
import json
import re
from pathlib import Path
import subprocess
import shutil
import threading
import time
import uuid


class SandboxUnavailable(RuntimeError):
    pass


class SECURITY_CAPABILITIES(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("capabilities", C.c_void_p),
                ("count", W.DWORD), ("reserved", W.DWORD)]


class STARTUPINFO(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR),
                ("title", W.LPWSTR), ("x", W.DWORD), ("y", W.DWORD),
                ("xsize", W.DWORD), ("ysize", W.DWORD), ("xchars", W.DWORD),
                ("ychars", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved_size", W.WORD),
                ("reserved_ptr", C.c_void_p), ("stdin", W.HANDLE),
                ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class STARTUPINFOEX(C.Structure):
    _fields_ = [("startup", STARTUPINFO), ("attributes", C.c_void_p)]


class PROCESS_INFORMATION(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE),
                ("pid", W.DWORD), ("tid", W.DWORD)]


class BASIC_LIMITS(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong),
                ("flags", W.DWORD), ("min_working_set", C.c_size_t),
                ("max_working_set", C.c_size_t), ("active_processes", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD),
                ("scheduling", W.DWORD)]


class IO_COUNTERS(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in
                ("reads", "writes", "other", "read_bytes", "write_bytes", "other_bytes")]


class EXTENDED_LIMITS(C.Structure):
    _fields_ = [("basic", BASIC_LIMITS), ("io", IO_COUNTERS),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class ACCOUNTING(C.Structure):
    _fields_ = [("user_time", C.c_longlong), ("kernel_time", C.c_longlong),
                ("period_user_time", C.c_longlong), ("period_kernel_time", C.c_longlong),
                ("page_faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


def _api():
    if os.name != "nt":
        raise SandboxUnavailable("The AppContainer probe requires Windows.")
    kernel = C.WinDLL("kernel32", use_last_error=True)
    userenv = C.WinDLL("userenv", use_last_error=True)
    advapi = C.WinDLL("advapi32", use_last_error=True)
    signatures = {
        "InitializeProcThreadAttributeList": ([C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL),
        "UpdateProcThreadAttribute": ([C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL),
        "DeleteProcThreadAttributeList": ([C.c_void_p], None),
        "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(STARTUPINFOEX), C.POINTER(PROCESS_INFORMATION)], W.BOOL),
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        "GetProcessTimes": ([W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "LocalFree": ([C.c_void_p], C.c_void_p),
        "GetWindowsDirectoryW": ([W.LPWSTR, W.UINT], W.UINT),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    userenv.CreateAppContainerProfile.argtypes = [W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, C.POINTER(C.c_void_p)]
    userenv.CreateAppContainerProfile.restype = C.c_long
    userenv.DeleteAppContainerProfile.argtypes = [W.LPCWSTR]
    userenv.DeleteAppContainerProfile.restype = C.c_long
    advapi.ConvertSidToStringSidW.argtypes = [C.c_void_p, C.POINTER(W.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = W.BOOL
    advapi.FreeSid.argtypes = [C.c_void_p]
    advapi.FreeSid.restype = C.c_void_p
    return kernel, userenv, advapi


def _check(result):
    if not result:
        raise C.WinError(C.get_last_error())
    return result


def _remove_scratch(root):
    # Windows can briefly retain an executable image after the last process
    # terminates. Retry only this exact owned directory, never its parent.
    deadline = time.monotonic() + 3
    while True:
        try:
            shutil.rmtree(root)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def _process_identity(kernel, pid):
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        if C.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists
            return None
        raise C.WinError(C.get_last_error())
    try:
        if kernel.WaitForSingleObject(handle, 0) == 0:
            return None
        created, ended, system, user = (W.FILETIME() for _ in range(4))
        _check(kernel.GetProcessTimes(handle, C.byref(created), C.byref(ended), C.byref(system), C.byref(user)))
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def _resources(kernel, userenv, advapi, parent):
    run_id = uuid.uuid4().hex
    root = Path(parent).resolve() / ("rasputin-probe-" + run_id)
    root.mkdir()  # fail on collision; never adopt an existing directory
    profile = "Rasputin.Probe." + run_id
    sid = C.c_void_p()
    created = False
    try:
        # Host-only metadata precedes profile creation so a crash is recoverable.
        # PID plus creation time prevents a reused PID from claiming this lease.
        lease = {"version": 1, "run_id": run_id, "owner_pid": os.getpid(),
                 "owner_started": _process_identity(kernel, os.getpid())}
        with (root / "lease.json").open("x", encoding="utf-8") as record:
            json.dump(lease, record)
            record.flush()
            os.fsync(record.fileno())
        hr = userenv.CreateAppContainerProfile(profile, profile, "Disposable execution probe", None, 0, C.byref(sid))
        if hr:
            raise SandboxUnavailable(f"AppContainer profile creation failed (HRESULT {hr:#x}).")
        created = True
        yield root, sid
    finally:
        if sid:
            advapi.FreeSid(sid)
        if created:
            hr = userenv.DeleteAppContainerProfile(profile)
            if hr:
                # Retain the lease if profile cleanup needs retry after restart.
                raise SandboxUnavailable(f"Probe profile cleanup failed (HRESULT {hr:#x}).")
        _remove_scratch(root)


def recover_abandoned(scratch_parent):
    """Recover only valid, dead-owner leases beneath an operator-selected root.

    Unreadable identities, malformed records and reparse points are retained for
    inspection. This diagnostic is not automatically run against application data.
    """
    kernel, userenv, _ = _api()
    parent = Path(scratch_parent).resolve(strict=True)
    results = []
    for root in parent.glob("rasputin-probe-*"):
        if not re.fullmatch(r"rasputin-probe-[0-9a-f]{32}", root.name):
            continue
        record = root / "lease.json"
        try:
            # Never follow a redirected root or lease when deciding ownership.
            if root.lstat().st_file_attributes & 0x400 or record.lstat().st_file_attributes & 0x400:
                raise ValueError("reparse point")
            if record.stat().st_size > 4096:
                raise ValueError("oversized lease")
            lease = json.loads(record.read_text(encoding="utf-8"))
            run_id = root.name.removeprefix("rasputin-probe-")
            if (not isinstance(lease, dict) or lease.get("version") != 1 or lease.get("run_id") != run_id
                    or type(lease.get("owner_pid")) is not int or not 0 < lease["owner_pid"] <= 0xFFFFFFFF
                    or type(lease.get("owner_started")) is not int or lease["owner_started"] <= 0):
                raise ValueError("invalid lease")
            if _process_identity(kernel, lease["owner_pid"]) == lease["owner_started"]:
                results.append({"run_id": run_id, "status": "active"})
                continue
            # Derive the profile from the owned directory; accept no deletion path
            # or profile name from a mutable JSON field.
            hr = userenv.DeleteAppContainerProfile("Rasputin.Probe." + run_id)
            if hr and (hr & 0xFFFFFFFF) not in (0x80070002, 0x80070003):
                raise SandboxUnavailable("Abandoned profile could not be removed.")
            _remove_scratch(root)
            results.append({"run_id": run_id, "status": "recovered"})
        except (OSError, ValueError, SandboxUnavailable):
            results.append({"run_id": root.name.removeprefix("rasputin-probe-"), "status": "retained"})
    return results


def probe(executable, files, arguments, *, scratch_parent, timeout=10, cancel=None,
          max_output=65536, memory_limit_mb=1024, max_processes=16):
    """Run an explicit fixture argv in a fresh disposable low-privilege container.

    The caller supplies a trusted absolute toolchain path and in-memory fixture
    files; no host checkout is mounted or copied. This is a synchronous diagnostic,
    deliberately unavailable to model-authored requests. No shell interpretation,
    network capabilities, inherited environment, or fallback execution.
    """
    kernel, userenv, advapi = _api()
    executable = Path(executable)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("Select an existing absolute fixture toolchain executable.")
    if not 0 < timeout <= 60 or not 0 < max_output <= 1048576:
        raise ValueError("Probe limits must be bounded.")
    if (type(memory_limit_mb) is not int or not 64 <= memory_limit_mb <= 1024
            or type(max_processes) is not int or not 1 <= max_processes <= 16):
        raise ValueError("Probe memory and process limits must be bounded.")
    if not isinstance(arguments, (list, tuple)) or not all(isinstance(arg, str) and "\0" not in arg for arg in arguments):
        raise ValueError("Arguments must be strings without NUL characters.")
    fixture_files = {}
    for name, content in files.items():
        relative = Path(name)
        if relative.is_absolute() or relative.drive or ".." in relative.parts or ":" in name:
            raise ValueError("Fixture paths must stay inside the disposable directory.")
        if not isinstance(content, str) or "\0" in name:
            raise ValueError("Fixture files must contain text and valid relative paths.")
        fixture_files[relative] = content
    with _resources(kernel, userenv, advapi, scratch_parent) as (root, sid):
        workspace = root / "workspace"
        workspace.mkdir()
        for relative, content in fixture_files.items():
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        # The prototype supports self-contained executables only. Keep the
        # toolchain in scratch rather than granting access to its host folder.
        toolchain = root / "toolchain"
        toolchain.mkdir()
        copied_executable = toolchain / executable.name
        shutil.copyfile(executable, copied_executable)
        sid_text = W.LPWSTR()
        _check(advapi.ConvertSidToStringSidW(sid, C.byref(sid_text)))
        try:
            windows = C.create_unicode_buffer(32768)
            _check(kernel.GetWindowsDirectoryW(windows, len(windows)))
            icacls = str(Path(windows.value) / "System32" / "icacls.exe")
            # Keep the toolchain and host-only lease outside writable scope.
            for target, options in ((workspace, ["/grant", f"*{sid_text.value}:(OI)(CI)M"]),
                                    (workspace, ["/setintegritylevel", "(OI)(CI)L"]),
                                    (toolchain, ["/grant", f"*{sid_text.value}:(OI)(CI)RX"])):
                subprocess.run([icacls, str(target), *options], check=True,
                               capture_output=True, creationflags=0x08000000)
        finally:
            kernel.LocalFree(sid_text)
        return _execute(kernel, sid, copied_executable, workspace, arguments, windows.value,
                        timeout, cancel, max_output, memory_limit_mb, max_processes)


def _execute(kernel, sid, executable, root, arguments, windows, timeout, cancel, max_output,
             memory_limit_mb, max_processes):
    import msvcrt

    job = None
    info = PROCESS_INFORMATION()
    attribute_list = None
    initialized = False
    descriptors = []
    readers = []
    chunks = bytearray()
    truncated = threading.Event()
    output_lock = threading.Lock()
    reason = "exited"
    started = time.monotonic()

    def drain(fd):
        try:
            while True:
                block = os.read(fd, 8192)
                if not block:
                    return
                with output_lock:
                    remaining = max_output - len(chunks)
                    chunks.extend(block[:remaining])
                    if len(block) > remaining:
                        truncated.set()
        finally:
            os.close(fd)

    try:
        out_read, out_write = os.pipe()
        descriptors.append(out_write)
        stdin = os.open(os.devnull, os.O_RDONLY)
        descriptors.append(stdin)
        for fd in descriptors:
            os.set_inheritable(fd, True)
        handles = (W.HANDLE * 2)(msvcrt.get_osfhandle(stdin), msvcrt.get_osfhandle(out_write))
        reader = threading.Thread(target=drain, args=(out_read,), daemon=True)
        reader.start()
        readers.append(reader)
        job = _check(kernel.CreateJobObjectW(None, None))
        limits = EXTENDED_LIMITS()
        limits.basic.flags = 0x2000 | 0x200 | 0x8  # kill on close, job memory, active processes
        limits.basic.active_processes = max_processes
        limits.job_memory = memory_limit_mb * 1024 * 1024
        _check(kernel.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
        size = C.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 3, 0, C.byref(size))
        attribute_list = C.create_string_buffer(size.value)
        _check(kernel.InitializeProcThreadAttributeList(attribute_list, 3, 0, C.byref(size)))
        initialized = True
        capabilities = SECURITY_CAPABILITIES(sid, None, 0, 0)
        jobs = (W.HANDLE * 1)(job)
        for key, value in ((0x20009, capabilities), (0x20002, handles), (0x2000D, jobs)):
            _check(kernel.UpdateProcThreadAttribute(attribute_list, 0, key, C.byref(value), C.sizeof(value), None, None))
        startup = STARTUPINFOEX()
        startup.startup.cb = C.sizeof(startup)
        startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles[0], handles[1], handles[1]
        startup.attributes = C.cast(attribute_list, C.c_void_p)
        # Windows resolves the new profile under LOCALAPPDATA during creation.
        # Supplying its path does not grant the child access to the host directory.
        local_appdata = os.environ.get("LOCALAPPDATA")
        if not local_appdata:
            raise SandboxUnavailable("Windows profile storage could not be resolved.")
        env = {"SystemRoot": windows, "WINDIR": windows, "LOCALAPPDATA": local_appdata,
               "TEMP": str(root), "TMP": str(root),
               "PATH": str(executable.parent) + os.pathsep + str(Path(windows) / "System32")}
        environment = C.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(env.items())) + "\0\0")
        command = C.create_unicode_buffer(subprocess.list2cmdline([str(executable), *arguments]))
        # Atomic job assignment prevents orphaned suspended children if the owner
        # dies between CreateProcess and token verification/ResumeThread.
        _check(kernel.CreateProcessW(str(executable), command, None, None, True,
                                    0x80000 | 0x400 | 0x4 | 0x08000000, environment,
                                    str(root), C.byref(startup), C.byref(info)))
        advapi = C.WinDLL("advapi32", use_last_error=True)
        advapi.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
        advapi.OpenProcessToken.restype = W.BOOL
        advapi.GetTokenInformation.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
        advapi.GetTokenInformation.restype = W.BOOL
        token = W.HANDLE()
        _check(advapi.OpenProcessToken(info.process, 0x8, C.byref(token)))
        try:
            is_container, returned = W.DWORD(), W.DWORD()
            _check(advapi.GetTokenInformation(token, 29, C.byref(is_container), C.sizeof(is_container), C.byref(returned)))
            if is_container.value != 1:
                raise SandboxUnavailable("Windows did not create an AppContainer token.")
        finally:
            kernel.CloseHandle(token)
        if kernel.ResumeThread(info.thread) == 0xFFFFFFFF:
            raise C.WinError(C.get_last_error())
        while True:
            status = kernel.WaitForSingleObject(info.process, 25)
            if status == 0:
                break
            if status != 258:
                raise C.WinError(C.get_last_error())
            if cancel and cancel.is_set():
                reason = "cancelled"
                break
            if time.monotonic() - started >= timeout:
                reason = "timeout"
                break
            if truncated.is_set():
                reason = "output_limit"
                break
        _check(kernel.TerminateJobObject(job, 1))  # descendants die even when their parent exits
        deadline = time.monotonic() + 5
        while True:
            accounting = ACCOUNTING()
            _check(kernel.QueryInformationJobObject(job, 1, C.byref(accounting), C.sizeof(accounting), None))
            if not accounting.active:
                break
            if time.monotonic() >= deadline:
                raise SandboxUnavailable("Probe descendants did not terminate.")
            time.sleep(0.025)
        if kernel.WaitForSingleObject(info.process, 5000) != 0:
            raise SandboxUnavailable("Probe process did not terminate.")
        exit_code = W.DWORD()
        _check(kernel.GetExitCodeProcess(info.process, C.byref(exit_code)))
    finally:
        if info.process:
            kernel.TerminateProcess(info.process, 1)
        if job:
            kernel.CloseHandle(job)
        for handle in (info.thread, info.process):
            if handle:
                kernel.CloseHandle(handle)
        for fd in descriptors:
            os.close(fd)
        for reader in readers:
            reader.join(timeout=5)
        if initialized:
            kernel.DeleteProcThreadAttributeList(attribute_list)
    if any(reader.is_alive() for reader in readers):
        raise SandboxUnavailable("Probe output pipe remained open after job termination.")
    if truncated.is_set() and reason == "exited":
        reason = "output_limit"
    return {"ran": True, "boundary": "windows_appcontainer_probe", "production_ready": False,
            "exit_code": exit_code.value, "termination_reason": reason,
            "output": bytes(chunks).decode("utf-8", errors="replace"),
            "truncated": truncated.is_set(), "duration_seconds": time.monotonic() - started}
