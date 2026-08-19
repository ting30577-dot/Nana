"""Process-memory authority for one-use D3 local export targets."""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import os
import secrets
import stat
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from nana_sidecar.sse import LocalSession


_MAX_TTL_SECONDS = 60 * 60
_FIXED_DRIVE = 3
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_CLOUD_COMPONENT_PREFIXES = (
    "onedrive",
    "dropbox",
    "google drive",
    "icloud drive",
    "box",
    "sharepoint",
)


class ExportSelectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExportSelectionSummary:
    selection_id: str
    label: str
    expires_at: str
    provenance: Literal["interactive_user", "test_harness"]


@dataclass(slots=True)
class _Selection:
    selection_id: str
    actor_id: str
    raw_path: Path
    handle: int | None
    identity: tuple[int, int]
    identity_digest: str
    target_commitment: str
    label: str
    expires_at: datetime
    expires_monotonic: float
    provenance: Literal["interactive_user", "test_harness"]
    state: Literal["available", "reserved", "bound", "closed"] = "available"
    command_id: str | None = None
    request_hash: str | None = None
    run_id: str | None = None
    action_id: str | None = None


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("file_attributes", ctypes.c_uint32),
        ("creation_time_low", ctypes.c_uint32),
        ("creation_time_high", ctypes.c_uint32),
        ("last_access_time_low", ctypes.c_uint32),
        ("last_access_time_high", ctypes.c_uint32),
        ("last_write_time_low", ctypes.c_uint32),
        ("last_write_time_high", ctypes.c_uint32),
        ("volume_serial_number", ctypes.c_uint32),
        ("file_size_high", ctypes.c_uint32),
        ("file_size_low", ctypes.c_uint32),
        ("number_of_links", ctypes.c_uint32),
        ("file_index_high", ctypes.c_uint32),
        ("file_index_low", ctypes.c_uint32),
    ]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        path.is_symlink()
        or bool(flag and attributes & flag)
        or getattr(os.path, "isjunction", lambda _path: False)(path)
    )


def _directory_is_empty(path: Path) -> bool:
    with os.scandir(path) as entries:
        return next(entries, None) is None


def _is_cloud_component(component: str) -> bool:
    normalized = component.strip().casefold()
    return normalized == ".dropbox.cache" or any(
        normalized == prefix
        or normalized.startswith(prefix + " ")
        or normalized.startswith(prefix + " -")
        or normalized.startswith(prefix + " (")
        for prefix in _CLOUD_COMPONENT_PREFIXES
    )


def _reject_reparse_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if _is_reparse(current):
                raise ExportSelectionError(
                    "E_SELECTION_REPARSE",
                    "export target contains a reparse component",
                )
        except OSError as exc:
            raise ExportSelectionError(
                "E_SELECTION_IDENTITY",
                "export target identity could not be verified",
            ) from exc


def _windows_handle(path: Path) -> tuple[int, tuple[int, int], Path]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        0x00000080,  # FILE_READ_ATTRIBUTES
        # Share reads and writes, but deliberately omit FILE_SHARE_DELETE.
        # Some supported Windows builds still permit directory rename, so the
        # retained identity is rechecked around every external operation too.
        0x00000001 | 0x00000002,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE or handle is None:
        raise ExportSelectionError(
            "E_SELECTION_HANDLE",
            "export target directory handle could not be retained",
        )
    info = _ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
        kernel32.CloseHandle(handle)
        raise ExportSelectionError(
            "E_SELECTION_IDENTITY",
            "export target filesystem identity could not be read",
        )
    size = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
    if size <= 0:
        kernel32.CloseHandle(handle)
        raise ExportSelectionError(
            "E_SELECTION_FINAL_PATH",
            "export target final path could not be verified",
        )
    buffer = ctypes.create_unicode_buffer(size + 1)
    if kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0) <= 0:
        kernel32.CloseHandle(handle)
        raise ExportSelectionError(
            "E_SELECTION_FINAL_PATH",
            "export target final path could not be verified",
        )
    final = buffer.value
    if final.startswith("\\\\?\\UNC\\"):
        kernel32.CloseHandle(handle)
        raise ExportSelectionError("E_SELECTION_NETWORK", "network targets are forbidden")
    if final.startswith("\\\\?\\"):
        final = final[4:]
    identity = (
        int(info.volume_serial_number),
        (int(info.file_index_high) << 32) | int(info.file_index_low),
    )
    return int(handle), identity, Path(final)


def _close_windows_handle(handle: int | None) -> None:
    if handle is not None and os.name == "nt":
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)


def _validate_windows_volume(path: Path) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    volume_buffer = ctypes.create_unicode_buffer(32768)
    if not kernel32.GetVolumePathNameW(str(path), volume_buffer, len(volume_buffer)):
        raise ExportSelectionError(
            "E_SELECTION_VOLUME",
            "export target volume could not be verified",
        )
    volume_root = volume_buffer.value
    if kernel32.GetDriveTypeW(volume_root) != _FIXED_DRIVE:
        raise ExportSelectionError(
            "E_SELECTION_NETWORK",
            "export target must be on a fixed local drive",
        )
    filesystem = ctypes.create_unicode_buffer(256)
    if not kernel32.GetVolumeInformationW(
        volume_root,
        None,
        0,
        None,
        None,
        None,
        filesystem,
        len(filesystem),
    ):
        raise ExportSelectionError(
            "E_SELECTION_VOLUME",
            "export target filesystem could not be verified",
        )
    if filesystem.value.upper() != "NTFS":
        raise ExportSelectionError(
            "E_SELECTION_FILESYSTEM",
            "only the audited fixed-local NTFS target is supported",
        )
    drive = path.drive
    device = ctypes.create_unicode_buffer(32768)
    if not drive or not kernel32.QueryDosDeviceW(drive, device, len(device)):
        raise ExportSelectionError(
            "E_SELECTION_VOLUME",
            "export target device mapping could not be verified",
        )
    if device.value.startswith("\\??\\"):
        raise ExportSelectionError("E_SELECTION_SUBST", "SUBST targets are forbidden")


class ExportSelectionRegistry:
    """Keep raw target authority and handles out of SQLite and browser state."""

    def __init__(
        self,
        *,
        session: LocalSession,
        workspace_root: str | Path,
        application_root: str | Path | None = None,
        actor_id: str,
        ttl_seconds: int = _MAX_TTL_SECONDS,
        utc_now: Callable[[], datetime] = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        allow_test_harness: bool = False,
    ) -> None:
        if not 1 <= ttl_seconds <= _MAX_TTL_SECONDS:
            raise ValueError("selection ttl must be between 1 and 3600 seconds")
        if not actor_id.strip():
            raise ValueError("selection actor id is required")
        self._session_key = session.token.get_secret_value().encode("ascii")
        self._workspace_root = Path(workspace_root).resolve(strict=True)
        self._application_root = Path(
            application_root or Path(__file__).resolve().parents[1]
        ).resolve(strict=True)
        self._actor_id = actor_id
        self._ttl_seconds = ttl_seconds
        self._utc_now = utc_now
        self._monotonic = monotonic
        self._allow_test_harness = allow_test_harness
        self._entries: dict[str, _Selection] = {}
        self._lock = threading.RLock()

    def register_interactive_target(self, raw_path: str) -> ExportSelectionSummary:
        return self._register(raw_path, provenance="interactive_user", test_harness=False)

    def register_test_harness_target(self, raw_path: str) -> ExportSelectionSummary:
        if not self._allow_test_harness:
            raise ExportSelectionError(
                "E_TEST_HARNESS_DISABLED",
                "test harness target registration is disabled",
            )
        return self._register(raw_path, provenance="test_harness", test_harness=True)

    def _register(
        self,
        raw_path: str,
        *,
        provenance: Literal["interactive_user", "test_harness"],
        test_harness: bool,
    ) -> ExportSelectionSummary:
        if not raw_path or "\x00" in raw_path:
            raise ExportSelectionError("E_SELECTION_PATH", "export target path is invalid")
        supplied = Path(raw_path)
        if not supplied.is_absolute() or str(supplied).startswith(("\\\\", "//")):
            raise ExportSelectionError(
                "E_SELECTION_PATH",
                "export target must be an absolute fixed-local path",
            )
        if any("~" in part for part in supplied.parts):
            raise ExportSelectionError("E_SELECTION_ALIAS", "short-path aliases are forbidden")
        try:
            if not supplied.is_dir():
                raise ExportSelectionError(
                    "E_SELECTION_DIRECTORY",
                    "export target must be an existing directory",
                )
            _reject_reparse_components(supplied)
            resolved = supplied.resolve(strict=True)
        except ExportSelectionError:
            raise
        except OSError as exc:
            raise ExportSelectionError(
                "E_SELECTION_IDENTITY",
                "export target could not be verified",
            ) from exc
        self._reject_dangerous_roots(resolved)
        if any(_is_cloud_component(part) for part in resolved.parts):
            raise ExportSelectionError(
                "E_SELECTION_CLOUD_SYNC",
                "cloud-synchronized targets are forbidden",
            )
        self._reject_configured_cloud_roots(resolved)
        if not _directory_is_empty(resolved):
            raise ExportSelectionError(
                "E_SELECTION_NOT_EMPTY",
                "export target must be a dedicated empty directory",
            )

        handle: int | None = None
        if os.name == "nt" and not test_harness:
            _validate_windows_volume(resolved)
            handle, identity, final = _windows_handle(resolved)
            supplied_text = os.path.normpath(str(supplied))
            final_text = os.path.normpath(str(final))
            if supplied_text != final_text:
                _close_windows_handle(handle)
                raise ExportSelectionError(
                    "E_SELECTION_ALIAS",
                    "export target aliases or case variants are forbidden",
                )
            resolved = final
        else:
            if not test_harness:
                raise ExportSelectionError(
                    "E_SELECTION_PLATFORM",
                    "real export selection is supported only on Windows",
                )
            metadata = resolved.stat()
            identity = (int(metadata.st_dev), int(metadata.st_ino))

        now = self._utc_now()
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        identity_material = (
            f"v1:{identity[0]}:{identity[1]}:"
            f"{self._workspace_root.stat().st_dev}:"
            f"{self._workspace_root.stat().st_ino}"
        ).encode("utf-8")
        identity_digest = "sha256:" + hmac.new(
            self._session_key,
            identity_material,
            hashlib.sha256,
        ).hexdigest()
        target_commitment = "sha256:" + hmac.new(
            self._session_key,
            (identity_digest + ":NANA_DRAFT_REPORT.md").encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        selection_id = secrets.token_urlsafe(32)
        entry = _Selection(
            selection_id=selection_id,
            actor_id=self._actor_id,
            raw_path=resolved,
            handle=handle,
            identity=identity,
            identity_digest=identity_digest,
            target_commitment=target_commitment,
            label="Dedicated local draft folder",
            expires_at=expires_at,
            expires_monotonic=self._monotonic() + self._ttl_seconds,
            provenance=provenance,
        )
        with self._lock:
            self._entries[selection_id] = entry
        return self._summary(entry)

    def summaries(self) -> tuple[ExportSelectionSummary, ...]:
        with self._lock:
            self._expire_locked()
            return tuple(
                self._summary(entry)
                for entry in self._entries.values()
                if entry.state != "closed"
            )

    def reserve(
        self,
        selection_id: str,
        *,
        actor_id: str,
        command_id: str,
        request_hash: str,
        run_id: str,
        action_id: str,
    ) -> _Selection:
        with self._lock:
            entry = self._require_live(selection_id, actor_id)
            binding = (command_id, request_hash, run_id, action_id)
            current = (
                entry.command_id,
                entry.request_hash,
                entry.run_id,
                entry.action_id,
            )
            if entry.state == "available":
                entry.state = "reserved"
                entry.command_id, entry.request_hash, entry.run_id, entry.action_id = binding
            elif entry.state in {"reserved", "bound"} and current == binding:
                pass
            else:
                raise ExportSelectionError(
                    "E_SELECTION_CONSUMED",
                    "export target selection is already bound to another attempt",
                )
            return entry

    def finalize(self, selection_id: str, *, command_id: str) -> None:
        with self._lock:
            entry = self._entries.get(selection_id)
            if entry is None or entry.command_id != command_id:
                raise ExportSelectionError(
                    "E_SELECTION_BINDING",
                    "export target reservation does not match the committed command",
                )
            if entry.state not in {"reserved", "bound"}:
                raise ExportSelectionError("E_SELECTION_CLOSED", "export selection is closed")
            entry.state = "bound"

    def release(self, selection_id: str, *, command_id: str) -> None:
        with self._lock:
            entry = self._entries.get(selection_id)
            if entry is None or entry.state != "reserved" or entry.command_id != command_id:
                return
            entry.state = "available"
            entry.command_id = None
            entry.request_hash = None
            entry.run_id = None
            entry.action_id = None

    def bound_for_action(self, action_id: str, *, actor_id: str) -> _Selection:
        with self._lock:
            self._expire_locked()
            matches = [
                entry
                for entry in self._entries.values()
                if entry.action_id == action_id
                and entry.actor_id == actor_id
                and entry.state == "bound"
            ]
            if len(matches) != 1:
                raise ExportSelectionError(
                    "E_SELECTION_UNAVAILABLE",
                    "the bound export target is no longer available",
                )
            self._validate_identity(matches[0])
            return matches[0]

    def revalidate_for_effect(
        self,
        action_id: str,
        *,
        actor_id: str,
        require_empty: bool,
    ) -> _Selection:
        """Re-check the retained directory identity immediately around effects."""

        with self._lock:
            self._expire_locked()
            matches = [
                entry
                for entry in self._entries.values()
                if entry.action_id == action_id
                and entry.actor_id == actor_id
                and entry.state == "bound"
            ]
            if len(matches) != 1:
                raise ExportSelectionError(
                    "E_SELECTION_UNAVAILABLE",
                    "the bound export target is no longer available",
                )
            self._validate_identity(matches[0], require_empty=require_empty)
            return matches[0]

    def close_action(self, action_id: str) -> None:
        with self._lock:
            for entry in self._entries.values():
                if entry.action_id == action_id and entry.state != "closed":
                    self._close_entry(entry)

    def close(self) -> None:
        with self._lock:
            for entry in self._entries.values():
                self._close_entry(entry)

    def _validate_identity(self, entry: _Selection, *, require_empty: bool = True) -> None:
        try:
            if require_empty and not _directory_is_empty(entry.raw_path):
                raise ExportSelectionError(
                    "E_SELECTION_CHANGED",
                    "export target is no longer empty",
                )
            _reject_reparse_components(entry.raw_path)
            if os.name == "nt" and entry.provenance == "interactive_user":
                probe_handle, identity, final = _windows_handle(entry.raw_path)
                _close_windows_handle(probe_handle)
                if identity != entry.identity or final != entry.raw_path:
                    raise ExportSelectionError(
                        "E_SELECTION_CHANGED",
                        "export target identity changed after selection",
                    )
            else:
                metadata = entry.raw_path.stat()
                if (int(metadata.st_dev), int(metadata.st_ino)) != entry.identity:
                    raise ExportSelectionError(
                        "E_SELECTION_CHANGED",
                        "export target identity changed after selection",
                    )
        except ExportSelectionError:
            raise
        except OSError as exc:
            raise ExportSelectionError(
                "E_SELECTION_IDENTITY",
                "export target identity could not be revalidated",
            ) from exc

    def _require_live(self, selection_id: str, actor_id: str) -> _Selection:
        self._expire_locked()
        entry = self._entries.get(selection_id)
        if entry is None or entry.state == "closed":
            raise ExportSelectionError(
                "E_SELECTION_UNAVAILABLE",
                "export target selection is unavailable",
            )
        if entry.actor_id != actor_id:
            raise ExportSelectionError(
                "E_SELECTION_ACTOR",
                "export target selection belongs to another actor",
            )
        self._validate_identity(entry)
        return entry

    def _expire_locked(self) -> None:
        now = self._monotonic()
        for entry in self._entries.values():
            if entry.state != "closed" and now >= entry.expires_monotonic:
                self._close_entry(entry)

    @staticmethod
    def _summary(entry: _Selection) -> ExportSelectionSummary:
        return ExportSelectionSummary(
            selection_id=entry.selection_id,
            label=entry.label,
            expires_at=_iso(entry.expires_at),
            provenance=entry.provenance,
        )

    @staticmethod
    def _close_entry(entry: _Selection) -> None:
        if entry.state != "closed":
            _close_windows_handle(entry.handle)
            entry.handle = None
            entry.state = "closed"

    def _reject_dangerous_roots(self, path: Path) -> None:
        def related(left: Path, right: Path) -> bool:
            return left == right or left.is_relative_to(right) or right.is_relative_to(left)

        if related(path, self._workspace_root) or related(path, self._application_root):
            raise ExportSelectionError(
                "E_SELECTION_NANA_SCOPE",
                "export target cannot contain or be contained by Nana or the Workspace",
            )
        if path == Path(path.anchor):
            raise ExportSelectionError("E_SELECTION_ROOT", "volume roots are forbidden")
        home = Path(os.path.abspath(os.path.expanduser("~")))
        if os.path.normcase(str(path)) == os.path.normcase(str(home)):
            raise ExportSelectionError("E_SELECTION_PROFILE", "the user profile root is forbidden")
        protected = {
            value
            for key in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")
            if (value := os.environ.get(key))
        }
        for value in protected:
            try:
                root = Path(value).resolve(strict=True)
            except OSError:
                continue
            if path == root or path.is_relative_to(root):
                raise ExportSelectionError(
                    "E_SELECTION_SYSTEM_SCOPE",
                    "system and program directories are forbidden",
                )

    @staticmethod
    def _reject_configured_cloud_roots(path: Path) -> None:
        names = (
            "OneDrive",
            "OneDriveCommercial",
            "OneDriveConsumer",
            "Dropbox",
            "GoogleDrive",
            "iCloudDrive",
        )
        for name in names:
            raw = os.environ.get(name)
            if not raw:
                continue
            try:
                root = Path(raw).resolve(strict=True)
            except OSError:
                continue
            if path == root or path.is_relative_to(root):
                raise ExportSelectionError(
                    "E_SELECTION_CLOUD_SYNC",
                    "cloud-synchronized targets are forbidden",
                )
