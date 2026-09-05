"""Windows Job ownership for trusted source-verification processes.

This is process lifetime control, not a filesystem/network sandbox. A suspended
Popen is assigned to a non-inheritable kill-on-close Job before its main thread
runs. Descendants cannot break away and remain owned after the wrapper exits.
No unsuspended launch or process-tree snapshot fallback is used.

Win32 contracts:
https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import subprocess
import time


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
    ]


def _kernel32():
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
        "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        "Thread32First": ([wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)], wintypes.BOOL),
        "Thread32Next": ([wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)], wintypes.BOOL),
        "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(dll, name)
        function.argtypes, function.restype = arguments, result
    return dll


def _winerror(operation):
    code = ctypes.get_last_error()
    return OSError(code, f"{operation}: {ctypes.FormatError(code).strip()}")


class _WindowsJob:
    def __init__(self):
        self.api = _kernel32()
        # NULL security attributes make the handle non-inheritable.
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise _winerror("CreateJobObjectW")
        try:
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE; no breakaway flags
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise _winerror("SetInformationJobObject")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise _winerror("CloseHandle(job)")
            self.handle = None

    def assign(self, process):
        # The process is suspended and Popen retains its original process handle,
        # so its PID cannot be reused during this operation.
        handle = self.api.OpenProcess(0x0100 | 0x0001, False, process.pid)  # SET_QUOTA | TERMINATE
        if not handle:
            raise _winerror("OpenProcess")
        try:
            if not self.api.AssignProcessToJobObject(self.handle, handle):
                raise _winerror("AssignProcessToJobObject")
        finally:
            self.api.CloseHandle(handle)

    def resume(self, process):
        # Popen closes CreateProcess's thread handle. Reopen only the main thread
        # of our still-suspended process using documented Toolhelp APIs.
        snapshot = self.api.CreateToolhelp32Snapshot(0x00000004, 0)  # SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise _winerror("CreateToolhelp32Snapshot")
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            found = self.api.Thread32First(snapshot, ctypes.byref(entry))
            threads = []
            while found:
                if entry.th32OwnerProcessID == process.pid:
                    threads.append(entry.th32ThreadID)
                entry.dwSize = ctypes.sizeof(entry)
                found = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise _winerror("Thread32Next")
            if len(threads) != 1:
                raise OSError("Suspended process did not have exactly one main thread.")
            thread = self.api.OpenThread(0x0002, False, threads[0])  # THREAD_SUSPEND_RESUME
            if not thread:
                raise _winerror("OpenThread")
            try:
                previous_count = self.api.ResumeThread(thread)
                if previous_count == 0xFFFFFFFF:
                    raise _winerror("ResumeThread")
                if previous_count != 1:
                    raise OSError("Unexpected main-thread suspend count; refusing uncertain startup.")
            finally:
                self.api.CloseHandle(thread)
        finally:
            self.api.CloseHandle(snapshot)

    def stop(self, timeout=10):
        if not self.handle:
            return
        try:
            if not self.api.TerminateJobObject(self.handle, 1):
                raise _winerror("TerminateJobObject")
            deadline = time.monotonic() + timeout
            while True:
                accounting = _Accounting()
                if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                    raise _winerror("QueryInformationJobObject")
                if accounting.ActiveProcesses == 0:
                    return
                if time.monotonic() >= deadline:
                    raise OSError("Owned process Job did not become empty before the cleanup deadline.")
                time.sleep(0.01)
        finally:
            # Also kills members if an exceptional cleanup path was reached.
            self.close()


def owned_popen(*args, **kwargs):
    """Return a regular Popen only after Windows descendant ownership is established."""
    if os.name != "nt":
        raise OSError("Reliable source-verification process ownership currently requires Windows.")
    flags = kwargs.get("creationflags", 0)
    if flags & 0x01000000:  # CREATE_BREAKAWAY_FROM_JOB
        raise OSError("Owned verification processes cannot request job breakaway.")
    kwargs["creationflags"] = flags | 0x00000004 | subprocess.CREATE_NO_WINDOW  # CREATE_SUSPENDED
    job = _WindowsJob()
    process = None
    try:
        process = subprocess.Popen(*args, **kwargs)
        job.assign(process)
        process._rasputin_owned_job = job
        job.resume(process)
        return process
    except BaseException:
        # On assignment failure the child is still suspended and has no children.
        # On later failure the Job owns every descendant. Never resume a fallback.
        try:
            if process is not None and process.poll() is None:
                process.kill()
            job.stop()
            if process is not None:
                process.wait(timeout=10)
        finally:
            job.close()
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
        raise


def stop_owned_process(process):
    """Stop an owned Job even if the direct child has already exited; safe to repeat."""
    job = getattr(process, "_rasputin_owned_job", None)
    if not isinstance(job, _WindowsJob):
        raise OSError("Process lacks retained Job ownership; launch it with owned_popen.")
    job.stop()
    process.wait(timeout=10)
    # Finish any communicate reader threads left by a timeout; this also closes
    # our PIPE streams after every writer in the Job has stopped.
    if process.stdout is not None or process.stderr is not None:
        process.communicate(timeout=10)
