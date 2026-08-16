"""Minimal Windows Job Object lifecycle for the trusted locked worker."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


WINDOWS_CREATE_SUSPENDED = 0x00000004


class WindowsJobError(RuntimeError):
    """Raised when a Windows worker cannot be bound to a kill-on-close Job."""


@dataclass(slots=True)
class WindowsJob:
    """Own a kill-on-close Job Object containing one locked worker tree."""

    _kernel32: object
    _handle: int
    _closed: bool = False

    @classmethod
    def assign(cls, process: subprocess.Popen[bytes]) -> "WindowsJob | None":
        if os.name != "nt":
            return None

        import ctypes
        from ctypes import wintypes

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BasicLimitInformation(ctypes.Structure):
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

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise WindowsJobError(
                f"CreateJobObjectW failed with error {ctypes.get_last_error()}"
            )
        handle_value = int(handle)
        information = ExtendedLimitInformation()
        information.BasicLimitInformation.LimitFlags = 0x00002000
        if not kernel32.SetInformationJobObject(
            wintypes.HANDLE(handle_value),
            9,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(wintypes.HANDLE(handle_value))
            raise WindowsJobError(
                f"SetInformationJobObject failed with error {error}"
            )
        process_handle = wintypes.HANDLE(int(getattr(process, "_handle")))
        if not kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(handle_value), process_handle
        ):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(wintypes.HANDLE(handle_value))
            raise WindowsJobError(
                f"AssignProcessToJobObject failed with error {error}"
            )
        return cls(kernel32, handle_value)

    def terminate(self, process: subprocess.Popen[bytes]) -> bool:
        if self._closed:
            return process.poll() is not None

        import ctypes
        from ctypes import wintypes

        if not self._kernel32.TerminateJobObject(
            wintypes.HANDLE(self._handle), 1
        ):
            return False
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return False
        return process.poll() is not None

    def resume(self, process: subprocess.Popen[bytes]) -> None:
        """Resume every thread of a process created with CREATE_SUSPENDED.

        ``subprocess.Popen`` closes the primary-thread handle returned by
        CreateProcess, so enumerate the still-suspended process threads only
        after the process has been assigned to this Job Object.
        """

        if self._closed:
            raise WindowsJobError("cannot resume a process from a closed Job")

        import ctypes
        from ctypes import wintypes

        class ThreadEntry32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD),
                ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG),
                ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
            ]

        kernel32 = self._kernel32
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
        kernel32.Thread32First.restype = wintypes.BOOL
        kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
        kernel32.Thread32Next.restype = wintypes.BOOL
        kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenThread.restype = wintypes.HANDLE
        kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
        kernel32.ResumeThread.restype = wintypes.DWORD

        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or int(snapshot) == invalid_handle:
            raise WindowsJobError(
                f"CreateToolhelp32Snapshot failed with error {ctypes.get_last_error()}"
            )

        resumed = 0
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(ThreadEntry32)
        try:
            has_entry = bool(kernel32.Thread32First(snapshot, ctypes.byref(entry)))
            while has_entry:
                if int(entry.th32OwnerProcessID) == process.pid:
                    thread = kernel32.OpenThread(
                        0x0002,
                        False,
                        entry.th32ThreadID,
                    )
                    if not thread:
                        raise WindowsJobError(
                            f"OpenThread failed with error {ctypes.get_last_error()}"
                        )
                    try:
                        previous_count = int(kernel32.ResumeThread(thread))
                    finally:
                        kernel32.CloseHandle(thread)
                    if previous_count == 0xFFFFFFFF:
                        raise WindowsJobError(
                            f"ResumeThread failed with error {ctypes.get_last_error()}"
                        )
                    if previous_count < 1:
                        raise WindowsJobError(
                            "worker thread was not suspended before Job assignment"
                        )
                    resumed += 1
                has_entry = bool(kernel32.Thread32Next(snapshot, ctypes.byref(entry)))
        finally:
            kernel32.CloseHandle(snapshot)

        if resumed < 1:
            raise WindowsJobError("suspended worker primary thread was not found")

    def suspend(self, process: subprocess.Popen[bytes]) -> None:
        """Suspend every current thread in the assigned worker process."""
        self._visit_threads(process, suspend=True)

    def resume_running(self, process: subprocess.Popen[bytes]) -> None:
        """Resume one suspension level on every current worker thread."""
        self._visit_threads(process, suspend=False)

    def _visit_threads(
        self, process: subprocess.Popen[bytes], *, suspend: bool
    ) -> None:
        if self._closed:
            raise WindowsJobError("cannot control a process from a closed Job")
        import ctypes
        from ctypes import wintypes

        class ThreadEntry32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD),
                ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
            ]

        kernel32 = self._kernel32
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
        kernel32.Thread32First.restype = wintypes.BOOL
        kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
        kernel32.Thread32Next.restype = wintypes.BOOL
        kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenThread.restype = wintypes.HANDLE
        operation = kernel32.SuspendThread if suspend else kernel32.ResumeThread
        operation.argtypes = [wintypes.HANDLE]
        operation.restype = wintypes.DWORD
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or int(snapshot) == invalid_handle:
            raise WindowsJobError(
                f"CreateToolhelp32Snapshot failed with error {ctypes.get_last_error()}"
            )
        controlled = 0
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(ThreadEntry32)
        try:
            has_entry = bool(kernel32.Thread32First(snapshot, ctypes.byref(entry)))
            while has_entry:
                if int(entry.th32OwnerProcessID) == process.pid:
                    thread = kernel32.OpenThread(0x0002, False, entry.th32ThreadID)
                    if not thread:
                        raise WindowsJobError(
                            f"OpenThread failed with error {ctypes.get_last_error()}"
                        )
                    try:
                        previous_count = int(operation(thread))
                    finally:
                        kernel32.CloseHandle(thread)
                    if previous_count == 0xFFFFFFFF:
                        raise WindowsJobError(
                            f"thread control failed with error {ctypes.get_last_error()}"
                        )
                    if not suspend and previous_count < 1:
                        raise WindowsJobError("worker thread was not paused")
                    controlled += 1
                has_entry = bool(kernel32.Thread32Next(snapshot, ctypes.byref(entry)))
        finally:
            kernel32.CloseHandle(snapshot)
        if controlled < 1:
            raise WindowsJobError("worker process has no controllable threads")

    def close(self) -> bool:
        if self._closed:
            return True

        from ctypes import wintypes

        closed = bool(self._kernel32.CloseHandle(wintypes.HANDLE(self._handle)))
        if not closed:
            return False
        self._closed = True
        return True
