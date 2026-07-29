"""Filesystem primitives for the D1 content-addressed Artifact store.

This module deliberately stops before SQLite lifecycle transactions.  It makes
partials durable, verifies content, and performs only same-volume promotion.
Canonical visibility remains controlled by the caller-provided Artifact state.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Mapping
from uuid import uuid4


class ArtifactIntegrityError(RuntimeError):
    """Artifact bytes do not match their declared content identity."""


class ArtifactNotAvailableError(FileNotFoundError):
    """The canonical Artifact state does not permit reading its blob."""


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    partial_path: Path
    temp_ref: str
    blob_hash: str
    size: int
    media_type: str
    was_cross_volume_copy: bool = False


def _default_volume_id(path: Path) -> str:
    resolved = path.resolve(strict=False)
    probe = resolved
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return str(probe.stat().st_dev)


def _default_flush(handle: BinaryIO) -> None:
    handle.flush()


def _default_write(handle: BinaryIO, content: memoryview) -> int:
    return handle.write(content)


_MEDIA_TYPE_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$"
)
_MIME_TYPES = mimetypes.MimeTypes()


class ArtifactStore:
    """Write and promote blobs inside one controlled Workspace volume."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        write: Callable[[BinaryIO, memoryview], int] = _default_write,
        flush: Callable[[BinaryIO], None] = _default_flush,
        fsync: Callable[[int], None] = os.fsync,
        replace: Callable[[Path, Path], None] = os.replace,
        volume_id: Callable[[Path], str] = _default_volume_id,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve(strict=False)
        self.artifacts_root = self.workspace_root / "artifacts"
        self.staging_root = self.artifacts_root / ".staging"
        self._write = write
        self._flush = flush
        self._fsync = fsync
        self._replace = replace
        self._volume_id = volume_id

    def blob_path(self, blob_hash: str) -> Path:
        digest = self._digest(blob_hash)
        return self.artifacts_root / "sha256" / digest[:2] / digest[2:4] / digest

    def stage_bytes(
        self,
        content: bytes,
        media_type: str,
        *,
        fail_after_bytes: int | None = None,
    ) -> StagedArtifact:
        normalized_media_type = self._normalize_media_type(media_type)
        if fail_after_bytes is not None and not (
            0 <= fail_after_bytes < len(content)
        ):
            raise ValueError(
                "fail_after_bytes must be strictly inside the content"
            )
        self.staging_root.mkdir(parents=True, exist_ok=True)
        partial_path = self.staging_root / f"{uuid4().hex}.partial"
        with partial_path.open("xb") as handle:
            if fail_after_bytes is not None:
                prefix = content[:fail_after_bytes]
                self._write_all(handle, prefix)
                self._flush(handle)
                raise OSError("injected partial write")
            self._write_all(handle, content)
            self._flush(handle)
            self._fsync(handle.fileno())
        blob_hash, size = self._measure(partial_path)
        return StagedArtifact(
            partial_path=partial_path,
            temp_ref=self._temp_ref(partial_path),
            blob_hash=blob_hash,
            size=size,
            media_type=normalized_media_type,
        )

    def stage_file(self, source: str | Path, media_type: str) -> StagedArtifact:
        source_path = Path(source).resolve(strict=True)
        normalized_media_type = self._normalize_media_type(media_type)
        detected_media_type = self._detect_file_media_type(source_path)
        if detected_media_type != normalized_media_type:
            raise ArtifactIntegrityError(
                "media type mismatch: "
                f"expected {normalized_media_type}, detected {detected_media_type}"
            )
        cross_volume = self._volume_id(source_path) != self._volume_id(
            self.staging_root
        )
        self.staging_root.mkdir(parents=True, exist_ok=True)
        partial_path = self.staging_root / f"{uuid4().hex}.partial"
        with source_path.open("rb") as source_handle:
            with partial_path.open("xb") as partial_handle:
                while chunk := source_handle.read(1024 * 1024):
                    self._write_all(partial_handle, chunk)
                self._flush(partial_handle)
                self._fsync(partial_handle.fileno())
        blob_hash, size = self._measure(partial_path)
        return StagedArtifact(
            partial_path=partial_path,
            temp_ref=self._temp_ref(partial_path),
            blob_hash=blob_hash,
            size=size,
            media_type=detected_media_type,
            was_cross_volume_copy=cross_volume,
        )

    def verify_staged(
        self,
        staged: StagedArtifact,
        *,
        expected_hash: str,
        expected_size: int,
        expected_media_type: str,
    ) -> None:
        self._require_workspace_partial(staged.partial_path)
        normalized_media_type = self._normalize_media_type(expected_media_type)
        self._digest(expected_hash)
        actual_temp_ref = self._temp_ref(staged.partial_path)
        if staged.temp_ref != actual_temp_ref:
            raise ArtifactIntegrityError(
                f"temp_ref mismatch: expected {actual_temp_ref}, "
                f"got {staged.temp_ref}"
            )
        if staged.blob_hash != expected_hash:
            raise ArtifactIntegrityError(
                f"hash mismatch: expected {expected_hash}, "
                f"got descriptor {staged.blob_hash}"
            )
        if staged.size != expected_size:
            raise ArtifactIntegrityError(
                f"size mismatch: expected {expected_size}, "
                f"got descriptor {staged.size}"
            )
        if staged.media_type != normalized_media_type:
            raise ArtifactIntegrityError(
                "media type mismatch: "
                f"expected {normalized_media_type}, got {staged.media_type}"
            )
        actual_hash, actual_size = self._measure(staged.partial_path)
        if actual_hash != staged.blob_hash:
            raise ArtifactIntegrityError(
                f"hash mismatch: expected {staged.blob_hash}, got {actual_hash}"
            )
        if actual_size != staged.size:
            raise ArtifactIntegrityError(
                f"size mismatch: expected {staged.size}, got {actual_size}"
            )

    def promote(self, staged: StagedArtifact) -> Path:
        self._require_workspace_partial(staged.partial_path)
        self.verify_staged(
            staged,
            expected_hash=staged.blob_hash,
            expected_size=staged.size,
            expected_media_type=staged.media_type,
        )
        final_path = self.blob_path(staged.blob_hash)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists() or final_path.is_symlink():
            try:
                self._verify_final(final_path, staged)
            except ArtifactIntegrityError as exc:
                raise ArtifactIntegrityError(
                    f"existing final blob is corrupt: {exc}"
                ) from exc
            staged.partial_path.unlink()
        else:
            if self._volume_id(staged.partial_path) != self._volume_id(final_path):
                raise OSError("staging and final Artifact paths are on different volumes")
            self._replace(staged.partial_path, final_path)
        return final_path

    def open_for_read(self, blob_hash: str, *, state: str) -> BinaryIO:
        if state != "available":
            raise ArtifactNotAvailableError(
                f"Artifact in state {state!r} is not available"
            )
        final_path = self.blob_path(blob_hash)
        if final_path.is_symlink():
            raise ArtifactIntegrityError(
                f"available Artifact blob is non-regular: {blob_hash}"
            )
        if not final_path.is_file():
            raise ArtifactNotAvailableError(f"available Artifact blob is missing: {blob_hash}")
        actual_hash, _ = self._measure(final_path)
        if actual_hash != blob_hash:
            raise ArtifactIntegrityError(
                f"available Artifact blob hash mismatch: {blob_hash}"
            )
        return final_path.open("rb")

    def verify_final(self, staged: StagedArtifact) -> Path:
        """Verify that the final content-addressed blob matches a stage."""

        final_path = self.blob_path(staged.blob_hash)
        self._verify_final(final_path, staged)
        return final_path

    def list_available_blob_hashes(
        self,
        artifact_states: Mapping[str, str] | None = None,
    ) -> tuple[str, ...]:
        """Return readable blobs whose canonical state is ``available``."""

        available: list[str] = []
        for blob_hash, state in (artifact_states or {}).items():
            if state != "available":
                continue
            with self.open_for_read(blob_hash, state=state):
                available.append(blob_hash)
        return tuple(sorted(available))

    def _verify_final(self, final_path: Path, staged: StagedArtifact) -> None:
        if final_path.is_symlink() or not final_path.is_file():
            raise ArtifactIntegrityError(
                f"non-regular final blob: {final_path}"
            )
        actual_hash, actual_size = self._measure(final_path)
        if actual_hash != staged.blob_hash:
            raise ArtifactIntegrityError(
                f"hash mismatch: expected {staged.blob_hash}, got {actual_hash}"
            )
        if actual_size != staged.size:
            raise ArtifactIntegrityError(
                f"size mismatch: expected {staged.size}, got {actual_size}"
            )

    def _require_workspace_partial(self, partial_path: Path) -> None:
        resolved = partial_path.resolve(strict=True)
        staging = self.staging_root.resolve(strict=False)
        if resolved.parent != staging or resolved.suffix != ".partial":
            raise ValueError("promotion source must be a Workspace staging .partial")

    def _temp_ref(self, partial_path: Path) -> str:
        return partial_path.relative_to(self.workspace_root).as_posix()

    def _write_all(self, handle: BinaryIO, content: bytes) -> None:
        remaining = memoryview(content)
        while remaining:
            written = self._write(handle, remaining)
            if written is None or written <= 0:
                raise OSError("Artifact partial write made no progress")
            if written > len(remaining):
                raise OSError("Artifact partial write reported an invalid byte count")
            remaining = remaining[written:]

    @staticmethod
    def _measure(path: Path) -> tuple[str, int]:
        hasher = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                hasher.update(chunk)
                size += len(chunk)
        return f"sha256:{hasher.hexdigest()}", size

    @staticmethod
    def _digest(blob_hash: str) -> str:
        prefix = "sha256:"
        digest = blob_hash.removeprefix(prefix)
        if not blob_hash.startswith(prefix) or len(digest) != 64:
            raise ValueError("blob_hash must be sha256:<64 lowercase hex characters>")
        if any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("blob_hash must be sha256:<64 lowercase hex characters>")
        return digest

    @staticmethod
    def _normalize_media_type(media_type: str) -> str:
        normalized = media_type.casefold()
        if (
            len(media_type) > 160
            or normalized != media_type.strip().casefold()
            or _MEDIA_TYPE_PATTERN.fullmatch(media_type) is None
        ):
            raise ValueError(
                "media_type must be a type/subtype token of at most 160 characters"
            )
        return normalized

    @classmethod
    def _detect_file_media_type(cls, source_path: Path) -> str:
        detected, encoding = _MIME_TYPES.guess_type(
            source_path.name,
            strict=False,
        )
        if encoding is not None:
            return "application/octet-stream"
        return cls._normalize_media_type(detected or "application/octet-stream")
