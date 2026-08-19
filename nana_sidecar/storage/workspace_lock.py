"""Process-exclusive Workspace ownership and lifecycle ordering."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
from pathlib import Path
import sqlite3
import stat
import sys
from typing import Callable

from nana_sidecar.storage.artifact_reconciliation import (
    ArtifactReconciler,
    ReconciliationReport,
)
from nana_sidecar.storage.artifacts import ArtifactStore
from nana_sidecar.storage.database import initialize_database


class WorkspaceLockError(RuntimeError):
    """Workspace ownership could not be acquired or released safely."""


class WorkspaceLock:
    """Hold an OS-level exclusive lock for the lifetime of a Workspace owner."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve(strict=False)
        self._handle: int | None = None
        self._file = None

    @property
    def is_held(self) -> bool:
        return self._handle is not None or self._file is not None

    def acquire(self) -> None:
        if self._handle is not None or self._file is not None:
            raise WorkspaceLockError("Workspace lock is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            self._acquire_windows()
        else:
            self._acquire_posix()

    def _acquire_windows(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.HANDLE,
        ]
        create_file.restype = ctypes.wintypes.HANDLE
        handle = create_file(
            str(self.path),
            0x40000000,  # GENERIC_WRITE
            0,  # no sharing: the OS owns the exclusivity decision
            None,
            4,  # OPEN_ALWAYS
            0x80,  # FILE_ATTRIBUTE_NORMAL
            None,
        )
        invalid = ctypes.wintypes.HANDLE(-1).value
        if handle == invalid:
            error = ctypes.get_last_error()
            raise WorkspaceLockError(
                f"Workspace lock is busy or unavailable (winerror={error})"
            )
        self._handle = int(handle)

    def _acquire_posix(self) -> None:
        import fcntl

        file = self.path.open("a+b")
        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            file.close()
            raise WorkspaceLockError("Workspace lock is busy") from exc
        self._file = file

    def release(self) -> None:
        if self._handle is None and self._file is None:
            raise WorkspaceLockError("Workspace lock is not held")
        if self._handle is not None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.wintypes.HANDLE]
            close_handle.restype = ctypes.wintypes.BOOL
            if not close_handle(ctypes.wintypes.HANDLE(self._handle)):
                error = ctypes.get_last_error()
                raise WorkspaceLockError(
                    f"Workspace lock close failed (winerror={error})"
                )
            self._handle = None
            return
        file = self._file
        self._file = None
        import fcntl

        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        finally:
            file.close()

    def __enter__(self) -> "WorkspaceLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class WorkspaceRuntime:
    """Own a canonical Workspace and enforce its startup/shutdown sequence."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        quiesce_writers: Callable[[], None] | None = None,
    ) -> None:
        target = Path(database_path)
        self.database_path = target.parent.resolve(strict=False) / target.name
        if self.database_path.exists() or self.database_path.is_symlink():
            metadata = self.database_path.lstat()
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            file_attributes = int(
                getattr(metadata, "st_file_attributes", 0)
            )
            is_reparse = self.database_path.is_symlink() or bool(
                reparse_flag and file_attributes & reparse_flag
            )
            is_junction = getattr(
                os.path,
                "isjunction",
                lambda _candidate: False,
            )(self.database_path)
            if is_reparse or is_junction:
                raise WorkspaceLockError(
                    "Canonical database must not be a reparse point"
                )
        expected_lock_path = self.database_path.with_name("workspace.owner.lock")
        self.lock = WorkspaceLock(expected_lock_path)
        if self.lock.path.parent != self.database_path.parent:
            raise WorkspaceLockError(
                "Workspace lock must resolve beside the canonical database"
            )
        self.quiesce_writers = quiesce_writers or (lambda: None)
        self.connection: sqlite3.Connection | None = None
        self.reconciliation_report: object | None = None
        self.state = "closed"

    def _reconcile_artifacts(
        self,
        connection: sqlite3.Connection,
    ) -> ReconciliationReport:
        store = ArtifactStore(self.database_path.parent)
        return ArtifactReconciler(connection, store).scan()

    def start(self) -> sqlite3.Connection:
        if self.state != "closed":
            raise WorkspaceLockError(f"Workspace runtime is {self.state}")
        self.state = "starting"
        try:
            # The lock is deliberately acquired before initialize_database can
            # open a writable connection or run migrations.
            self.lock.acquire()
            self.state = "locked"
            self.connection = initialize_database(self.database_path)
            self.state = "reconciling"
            self.reconciliation_report = self._reconcile_artifacts(
                self.connection
            )
            self.state = "ready"
            return self.connection
        except Exception:
            self._abort_start()
            raise

    def _abort_start(self) -> None:
        connection = self.connection
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                self.state = "startup_close_failed"
                raise WorkspaceLockError(
                    "Workspace startup failed and SQLite could not close; "
                    "ownership is retained"
                ) from exc
            self.connection = None
        if self.lock.is_held:
            try:
                self.lock.release()
            except Exception as exc:
                self.state = "lock_release_failed"
                raise WorkspaceLockError(
                    "Workspace startup failed and the OS lock could not release"
                ) from exc
        self.state = "closed"

    def close(self) -> None:
        if self.state == "closed":
            return
        if self.state != "ready":
            raise WorkspaceLockError(
                f"Workspace runtime cannot close from {self.state}"
            )
        self.state = "draining"
        connection = self.connection
        try:
            self.quiesce_writers()
        except Exception:
            self.state = "drain_failed"
            raise
        try:
            if connection is not None:
                connection.close()
        except Exception:
            # Fail closed: ownership is retained when SQLite cannot prove it is
            # closed. A caller must diagnose the locked Workspace rather than
            # allowing a second writer to enter.
            self.state = "close_failed"
            raise
        self.connection = None
        try:
            # The OS lock is released only after SQLite/WAL close succeeds.
            self.lock.release()
        except Exception:
            self.state = "lock_release_failed"
            raise
        else:
            self.state = "closed"

    def __enter__(self) -> "WorkspaceRuntime":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
