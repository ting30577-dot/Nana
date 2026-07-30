"""D1-02 tests for durable Artifact staging and metadata validation."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from nana_sidecar.contracts.domain import ArtifactStagedPayload
from nana_sidecar.storage.artifacts import (
    ArtifactIntegrityError,
    ArtifactStore,
    _default_volume_id,
)


ROOT = Path(__file__).resolve().parents[1]
RESOURCE = (
    ROOT
    / "fixtures"
    / "v0.3.0-dev"
    / "resources"
    / "variable-window-monotonicity.md"
)
RESOURCE_HASH = (
    "sha256:437fbf2320eacc59e01adc16503f5297383551b77c2457b1a054bcf4b7e5fe4a"
)


class RecordingArtifactStore(ArtifactStore):
    def __init__(self, workspace_root: Path, order: list[str]) -> None:
        def flush(handle: object) -> None:
            order.append("flush")
            handle.flush()  # type: ignore[attr-defined]

        def fsync(fd: int) -> None:
            order.append("fsync")
            os.fsync(fd)

        super().__init__(workspace_root, flush=flush, fsync=fsync)
        self.order = order

    def _measure(self, path: Path) -> tuple[str, int]:
        self.order.append("measure")
        return super()._measure(path)


class D1ArtifactStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name) / "workspace"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_stage_measures_only_after_flush_and_fsync(self) -> None:
        order: list[str] = []
        store = RecordingArtifactStore(self.workspace, order)

        staged = store.stage_bytes(b"measure after durability", "text/plain")

        self.assertEqual(order, ["flush", "fsync", "measure"])
        self.assertEqual(staged.size, 24)
        self.assertEqual(
            staged.blob_hash,
            "sha256:" + hashlib.sha256(b"measure after durability").hexdigest(),
        )

    def test_short_writes_are_retried_until_content_is_complete(self) -> None:
        def short_write(handle: object, content: memoryview) -> int:
            return handle.write(content[:3])  # type: ignore[attr-defined]

        store = ArtifactStore(self.workspace, write=short_write)
        payload = b"short writes must not truncate the staged artifact"

        staged = store.stage_bytes(payload, "text/plain")

        self.assertEqual(staged.partial_path.read_bytes(), payload)
        self.assertEqual(staged.size, len(payload))

    def test_zero_progress_write_fails_and_remains_invisible(self) -> None:
        def zero_write(handle: object, content: memoryview) -> int:
            return 0

        store = ArtifactStore(self.workspace, write=zero_write)

        with self.assertRaisesRegex(OSError, "made no progress"):
            store.stage_bytes(b"cannot disappear", "text/plain")

        self.assertEqual(len(list(store.staging_root.glob("*.partial"))), 1)
        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_stage_real_fixture_has_complete_portable_metadata(self) -> None:
        store = ArtifactStore(self.workspace)

        staged = store.stage_file(RESOURCE, "text/markdown")

        self.assertEqual(staged.blob_hash, RESOURCE_HASH)
        self.assertEqual(staged.size, RESOURCE.stat().st_size)
        self.assertEqual(staged.media_type, "text/markdown")
        self.assertEqual(staged.temp_ref, staged.partial_path.relative_to(self.workspace).as_posix())
        self.assertFalse(Path(staged.temp_ref).is_absolute())
        self.assertEqual(staged.partial_path.read_bytes(), RESOURCE.read_bytes())
        payload = ArtifactStagedPayload(
            artifact_id=uuid4(),
            temp_ref=staged.temp_ref,
            blob_hash=staged.blob_hash,
            size=staged.size,
            media_type=staged.media_type,
        )
        self.assertEqual(payload.temp_ref, staged.temp_ref)
        self.assertEqual(
            store.list_available_blob_hashes({staged.blob_hash: "staged"}),
            (),
        )
        self.assertFalse(store.blob_path(staged.blob_hash).exists())

    def test_file_media_type_mismatch_is_rejected_before_partial_write(self) -> None:
        store = ArtifactStore(self.workspace)

        with self.assertRaisesRegex(ArtifactIntegrityError, "media type mismatch"):
            store.stage_file(RESOURCE, "application/pdf")

        self.assertFalse(store.staging_root.exists())

    def test_file_media_type_mapping_does_not_depend_on_host_registry(self) -> None:
        store = ArtifactStore(self.workspace)

        with patch(
            "nana_sidecar.storage.artifacts.mimetypes.guess_type",
            return_value=("application/x-host-override", None),
        ):
            staged = store.stage_file(RESOURCE, "text/markdown")

        self.assertEqual(staged.media_type, "text/markdown")

    def test_invalid_media_type_is_rejected_before_partial_write(self) -> None:
        store = ArtifactStore(self.workspace)

        for media_type in ("", "text", "text /plain", "x" * 161):
            with self.subTest(media_type=media_type):
                with self.assertRaisesRegex(ValueError, "media_type"):
                    store.stage_bytes(b"payload", media_type)

        self.assertFalse(store.staging_root.exists())

    def test_verify_staged_checks_hash_size_and_media_type(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"verified stage", "text/plain")

        store.verify_staged(
            staged,
            expected_hash=staged.blob_hash,
            expected_size=staged.size,
            expected_media_type="text/plain",
        )
        with self.assertRaisesRegex(ArtifactIntegrityError, "media type mismatch"):
            store.verify_staged(
                staged,
                expected_hash=staged.blob_hash,
                expected_size=staged.size,
                expected_media_type="application/json",
            )

    def test_verify_staged_rejects_forged_descriptor_fields(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"descriptor identity", "text/plain")
        forged_descriptors = (
            (
                replace(staged, temp_ref="artifacts/.staging/other.partial"),
                "temp_ref mismatch",
            ),
            (
                replace(staged, blob_hash="sha256:" + "0" * 64),
                "hash mismatch",
            ),
            (replace(staged, size=staged.size + 1), "size mismatch"),
        )

        for forged, message in forged_descriptors:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ArtifactIntegrityError, message):
                    store.verify_staged(
                        forged,
                        expected_hash=staged.blob_hash,
                        expected_size=staged.size,
                        expected_media_type=staged.media_type,
                    )

    def test_existing_valid_blob_is_verified_and_reused(self) -> None:
        replacements: list[tuple[Path, Path]] = []

        def recording_replace(source: Path, destination: Path) -> None:
            replacements.append((source, destination))
            os.replace(source, destination)

        store = ArtifactStore(self.workspace, replace=recording_replace)
        first = store.stage_bytes(b"deduplicated", "text/plain")
        final_path = store.promote(first)
        second = store.stage_bytes(b"deduplicated", "text/plain")

        reused_path = store.promote(second)

        self.assertEqual(reused_path, final_path)
        self.assertEqual(len(replacements), 1)
        self.assertFalse(second.partial_path.exists())
        self.assertEqual(final_path.read_bytes(), b"deduplicated")

    def test_existing_non_regular_final_blob_is_rejected(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"regular files only", "text/plain")
        final_path = store.blob_path(staged.blob_hash)
        final_path.mkdir(parents=True)

        with self.assertRaisesRegex(
            ArtifactIntegrityError,
            "non-regular final blob",
        ):
            store.promote(staged)

        self.assertTrue(staged.partial_path.exists())

    def test_existing_final_symlink_is_rejected_before_reuse(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"do not follow links", "text/plain")
        final_path = store.blob_path(staged.blob_hash)
        final_path.parent.mkdir(parents=True)
        final_path.write_bytes(b"do not follow links")

        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(
                ArtifactIntegrityError,
                "non-regular final blob",
            ):
                store.promote(staged)

        self.assertTrue(staged.partial_path.exists())

    def test_default_volume_identity_uses_device_not_drive_letter(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"volume identity", "text/plain")

        self.assertEqual(
            _default_volume_id(staged.partial_path),
            str(os.stat(staged.partial_path).st_dev),
        )

    def test_workspace_artifact_ancestor_junction_is_rejected(self) -> None:
        store = ArtifactStore(self.workspace)
        store.artifacts_root.mkdir(parents=True)
        real_isjunction = getattr(os.path, "isjunction", lambda path: False)

        def injected_isjunction(path: object) -> bool:
            return (
                Path(path) == store.artifacts_root
                or real_isjunction(path)
            )

        with patch.object(
            os.path,
            "isjunction",
            side_effect=injected_isjunction,
            create=True,
        ):
            with self.assertRaisesRegex(
                ArtifactIntegrityError,
                "reparse point",
            ):
                store.stage_bytes(b"must stay in Workspace", "text/plain")

        self.assertFalse(store.staging_root.exists())


if __name__ == "__main__":
    unittest.main()
