"""D1-01 failure-first tests for the real Artifact filesystem boundary."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from nana_sidecar.storage.artifacts import (
    ArtifactIntegrityError,
    ArtifactNotAvailableError,
    ArtifactStore,
)


class D1ArtifactFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name) / "workspace"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_partial_write_leaves_only_invisible_partial(self) -> None:
        store = ArtifactStore(self.workspace)
        payload = b"complete payload"

        with self.assertRaisesRegex(OSError, "injected partial write"):
            store.stage_bytes(
                payload,
                "text/plain",
                fail_after_bytes=len(payload) // 2,
            )

        partials = list(store.staging_root.glob("*.partial"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), payload[: len(payload) // 2])
        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_invalid_partial_failure_position_is_rejected_before_write(self) -> None:
        store = ArtifactStore(self.workspace)
        payload = b"complete payload"

        for invalid_position in (-1, len(payload)):
            with self.subTest(invalid_position=invalid_position):
                with self.assertRaisesRegex(ValueError, "strictly inside"):
                    store.stage_bytes(
                        payload,
                        "text/plain",
                        fail_after_bytes=invalid_position,
                    )
        self.assertFalse(store.staging_root.exists())

    def test_flush_failure_never_promotes_partial(self) -> None:
        def failing_flush(handle: object) -> None:
            raise OSError("injected flush failure")

        store = ArtifactStore(self.workspace, flush=failing_flush)
        with self.assertRaisesRegex(OSError, "injected flush failure"):
            store.stage_bytes(b"flush before fsync", "text/plain")

        self.assertEqual(len(list(store.staging_root.glob("*.partial"))), 1)
        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_fsync_failure_never_promotes_partial(self) -> None:
        calls: list[int] = []

        def failing_fsync(fd: int) -> None:
            calls.append(fd)
            raise OSError("injected fsync failure")

        store = ArtifactStore(self.workspace, fsync=failing_fsync)
        with self.assertRaisesRegex(OSError, "injected fsync failure"):
            store.stage_bytes(b"durable only after fsync", "text/plain")

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(list(store.staging_root.glob("*.partial"))), 1)
        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_hash_or_size_mismatch_rejects_staged_content(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"verified payload", "text/plain")

        with self.assertRaisesRegex(ArtifactIntegrityError, "hash mismatch"):
            store.verify_staged(
                staged.partial_path,
                expected_hash="sha256:" + "0" * 64,
                expected_size=staged.size,
            )
        with self.assertRaisesRegex(ArtifactIntegrityError, "size mismatch"):
            store.verify_staged(
                staged.partial_path,
                expected_hash=staged.blob_hash,
                expected_size=staged.size + 1,
            )

        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_existing_final_blob_is_verified_before_reuse(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"canonical content", "text/plain")
        final_path = store.blob_path(staged.blob_hash)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(b"corrupt content")

        with self.assertRaisesRegex(
            ArtifactIntegrityError,
            "existing final blob is corrupt",
        ):
            store.promote(staged)

        self.assertTrue(staged.partial_path.exists())
        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_rename_failure_keeps_partial_and_exposes_no_blob(self) -> None:
        def failing_replace(source: Path, destination: Path) -> None:
            raise OSError("injected rename failure")

        store = ArtifactStore(self.workspace, replace=failing_replace)
        staged = store.stage_bytes(b"rename atomically", "text/plain")

        with self.assertRaisesRegex(OSError, "injected rename failure"):
            store.promote(staged)

        self.assertTrue(staged.partial_path.exists())
        self.assertFalse(store.blob_path(staged.blob_hash).exists())
        self.assertEqual(store.list_available_blob_hashes(), ())

    def test_cross_volume_input_is_copied_to_workspace_staging_first(self) -> None:
        source_root = Path(self.tempdir.name) / "external"
        source_root.mkdir()
        source = source_root / "input.txt"
        source.write_bytes(b"cross-volume input")
        replacements: list[tuple[Path, Path]] = []

        def volume(path: Path) -> str:
            return "external-volume" if source_root in path.parents else "workspace-volume"

        def recording_replace(source_path: Path, destination: Path) -> None:
            replacements.append((source_path, destination))
            os.replace(source_path, destination)

        store = ArtifactStore(
            self.workspace,
            volume_id=volume,
            replace=recording_replace,
        )
        staged = store.stage_file(source, "text/plain")
        final_path = store.promote(staged)

        self.assertTrue(staged.was_cross_volume_copy)
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0][0].parent, store.staging_root)
        self.assertEqual(replacements[0][1], final_path)
        self.assertEqual(final_path.read_bytes(), b"cross-volume input")
        self.assertTrue(source.exists())

    def test_partial_and_staged_artifact_are_invisible_to_reader(self) -> None:
        store = ArtifactStore(self.workspace)
        staged = store.stage_bytes(b"not committed", "text/plain")

        with self.assertRaises(ArtifactNotAvailableError):
            store.open_for_read(
                staged.blob_hash,
                state="staged",
            )
        self.assertEqual(store.list_available_blob_hashes(), ())

        final_path = store.promote(staged)
        with self.assertRaises(ArtifactNotAvailableError):
            store.open_for_read(
                staged.blob_hash,
                state="staged",
            )
        self.assertEqual(
            store.list_available_blob_hashes({staged.blob_hash: "staged"}),
            (),
        )
        with store.open_for_read(staged.blob_hash, state="available") as handle:
            self.assertEqual(handle.read(), b"not committed")
        self.assertEqual(
            store.list_available_blob_hashes(
                {staged.blob_hash: "available"}
            ),
            (staged.blob_hash,),
        )
        self.assertEqual(
            hashlib.sha256(final_path.read_bytes()).hexdigest(),
            staged.blob_hash.removeprefix("sha256:"),
        )


if __name__ == "__main__":
    unittest.main()
