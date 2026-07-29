"""Filesystem primitives for the D1 content-addressed Artifact store.

This module deliberately stops before SQLite lifecycle transactions.  It makes
partials durable, verifies content, and performs only same-volume promotion.
Canonical visibility remains controlled by the caller-provided Artifact state.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable
from uuid import uuid4


class ArtifactIntegrityError(RuntimeError):
    """Artifact bytes do not match their declared content identity."""


class ArtifactNotAvailableError(FileNotFoundError):
    """The canonical Artifact state does not permit reading its blob."""


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    partial_path: Path
    blob_hash: str
    size: int
    media_type: str
    was_cross_volume_copy: bool = False


def _default_volume_id(path: Path) -> str:
    resolved = path.resolve(strict=False)
    return resolved.drive.casefold() or resolved.anchor.casefold()


class ArtifactStore:
    """Write and promote blobs inside one controlled Workspace volume."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        fsync: Callable[[int], None] = os.fsync,
        replace: Callable[[Path, Path], None] = os.replace,
        volume_id: Callable[[Path], str] = _default_volume_id,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve(strict=False)
        self.artifacts_root = self.workspace_root / "artifacts"
        self.staging_root = self.artifacts_root / ".staging"
        self._fsync = fsync
        self._replace = replace
        self._volume_id = volume_id
        self._promoted_hashes: set[str] = set()

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
        self._validate_media_type(media_type)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        partial_path = self.staging_root / f"{uuid4().hex}.partial"
        hasher = hashlib.sha256()
        size = 0
        with partial_path.open("xb") as handle:
            if fail_after_bytes is not None:
                prefix = content[:fail_after_bytes]
                handle.write(prefix)
                hasher.update(prefix)
                size += len(prefix)
                handle.flush()
                raise OSError("injected partial write")
            handle.write(content)
            hasher.update(content)
            size = len(content)
            handle.flush()
            self._fsync(handle.fileno())
        return StagedArtifact(
            partial_path=partial_path,
            blob_hash=f"sha256:{hasher.hexdigest()}",
            size=size,
            media_type=media_type,
        )

    def stage_file(self, source: str | Path, media_type: str) -> StagedArtifact:
        source_path = Path(source).resolve(strict=True)
        staged = self.stage_bytes(source_path.read_bytes(), media_type)
        cross_volume = self._volume_id(source_path) != self._volume_id(
            self.staging_root
        )
        return StagedArtifact(
            partial_path=staged.partial_path,
            blob_hash=staged.blob_hash,
            size=staged.size,
            media_type=staged.media_type,
            was_cross_volume_copy=cross_volume,
        )

    def verify_staged(
        self,
        partial_path: str | Path,
        *,
        expected_hash: str,
        expected_size: int,
    ) -> None:
        actual_hash, actual_size = self._measure(Path(partial_path))
        if actual_hash != expected_hash:
            raise ArtifactIntegrityError(
                f"hash mismatch: expected {expected_hash}, got {actual_hash}"
            )
        if actual_size != expected_size:
            raise ArtifactIntegrityError(
                f"size mismatch: expected {expected_size}, got {actual_size}"
            )

    def promote(self, staged: StagedArtifact) -> Path:
        self._require_workspace_partial(staged.partial_path)
        self.verify_staged(
            staged.partial_path,
            expected_hash=staged.blob_hash,
            expected_size=staged.size,
        )
        final_path = self.blob_path(staged.blob_hash)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
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
        self._promoted_hashes.add(staged.blob_hash)
        return final_path

    def open_for_read(self, blob_hash: str, *, state: str) -> BinaryIO:
        if state != "available":
            raise ArtifactNotAvailableError(
                f"Artifact in state {state!r} is not available"
            )
        final_path = self.blob_path(blob_hash)
        if not final_path.is_file():
            raise ArtifactNotAvailableError(f"available Artifact blob is missing: {blob_hash}")
        actual_hash, _ = self._measure(final_path)
        if actual_hash != blob_hash:
            raise ArtifactIntegrityError(
                f"available Artifact blob hash mismatch: {blob_hash}"
            )
        return final_path.open("rb")

    def list_available_blob_hashes(self) -> tuple[str, ...]:
        """Return blobs promoted successfully by this store instance."""

        return tuple(sorted(self._promoted_hashes))

    def _verify_final(self, final_path: Path, staged: StagedArtifact) -> None:
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
    def _validate_media_type(media_type: str) -> None:
        if not media_type.strip():
            raise ValueError("media_type must not be empty")
