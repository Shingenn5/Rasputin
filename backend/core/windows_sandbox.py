"""Development-only Windows AppContainer execution probe.

Not registered as an agent tool or an execution authorization. Production shell and
validation remain disabled. Only disposable fixture files belong in this runner.
"""
from __future__ import annotations

import ctypes as C
from contextlib import contextmanager
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
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
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
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


@contextmanager
def _scratch(parent):
    root = Path(tempfile.mkdtemp(prefix="rasputin-probe-", dir=parent))
    try:
        yield root
    finally:
        # Windows can briefly retain an executable image after the last process
        # terminates. Retry only this exact newly allocated directory.
        deadline = time.monotonic() + 3
        while True:
            try:
                shutil.rmtree(root)
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)


def probe(executable, files, arguments, *, scratch_parent, timeout=10, cancel=None,
          max_output=65536):
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
    profile = "Rasputin.Probe." + uuid.uuid4().hex
    sid = C.c_void_p()
    hr = userenv.CreateAppContainerProfile(profile, profile, "Disposable execution probe", None, 0, C.byref(sid))
    if hr:
        raise SandboxUnavailable(f"AppContainer profile creation failed (HRESULT {hr:#x}).")
    try:
        with _scratch(scratch_parent) as root:
            for relative, content in fixture_files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            # The prototype supports self-contained executables only. Keep the
            # toolchain in scratch rather than granting access to its host folder.
            toolchain = root / ("toolchain-" + uuid.uuid4().hex)
            toolchain.mkdir()
            copied_executable = toolchain / executable.name
            shutil.copyfile(executable, copied_executable)
            sid_text = W.LPWSTR()
            _check(advapi.ConvertSidToStringSidW(sid, C.byref(sid_text)))
            try:
                windows = C.create_unicode_buffer(32768)
                _check(kernel.GetWindowsDirectoryW(windows, len(windows)))
                icacls = str(Path(windows.value) / "System32" / "icacls.exe")
                # Only this newly created disposable directory receives an ACL.
                for options in (["/grant", f"*{sid_text.value}:(OI)(CI)M"],
                                ["/setintegritylevel", "(OI)(CI)L"]):
                    subprocess.run([icacls, str(root), *options], check=True,
                                   capture_output=True, creationflags=0x08000000)
            finally:
                kernel.LocalFree(sid_text)
            return _execute(kernel, sid, copied_executable, root, arguments, windows.value,
                            timeout, cancel, max_output)
    finally:
        advapi.FreeSid(sid)
        hr = userenv.DeleteAppContainerProfile(profile)
        if hr:
            raise SandboxUnavailable(f"Probe profile cleanup failed (HRESULT {hr:#x}).")


def _execute(kernel, sid, executable, root, arguments, windows, timeout, cancel, max_output):
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
        size = C.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
        attribute_list = C.create_string_buffer(size.value)
        _check(kernel.InitializeProcThreadAttributeList(attribute_list, 2, 0, C.byref(size)))
        initialized = True
        capabilities = SECURITY_CAPABILITIES(sid, None, 0, 0)
        for key, value in ((0x20009, capabilities), (0x20002, handles)):
            _check(kernel.UpdateProcThreadAttribute(attribute_list, 0, key, C.byref(value), C.sizeof(value), None, None))
        job = _check(kernel.CreateJobObjectW(None, None))
        limits = EXTENDED_LIMITS()
        limits.basic.flags = 0x2000 | 0x200 | 0x8  # kill on close, job memory, active processes
        limits.basic.active_processes = 16
        limits.job_memory = 1024 * 1024 * 1024
        _check(kernel.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
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
        # Suspended creation closes the race between launch and job assignment.
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
        _check(kernel.AssignProcessToJobObject(job, info.process))
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
