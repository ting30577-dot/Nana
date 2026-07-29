"""D1-03 tests for the two-transaction Artifact commit protocol."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from nana_sidecar.storage import connect_database, initialize_database
from nana_sidecar.storage.artifact_commits import (
    ArtifactCommitService,
    ArtifactReader,
)
from nana_sidecar.storage.artifacts import (
    ArtifactIntegrityError,
    ArtifactNotAvailableError,
    ArtifactStore,
)


NOW = "2026-07-29T00:00:00Z"


class InjectedCrash(RuntimeError):
    pass


class D1ArtifactCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name) / "workspace"
        self.connection = initialize_database(self.workspace / "nana.db")
        self.store = ArtifactStore(self.workspace)
        self.reader = ArtifactReader(self.connection, self.store)

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _service(self, checkpoint=None) -> ArtifactCommitService:
        return ArtifactCommitService(
            self.connection,
            self.store,
            now=lambda: NOW,
            checkpoint=checkpoint,
        )

    def _stage(self, content: bytes = b"two phase payload"):
        return self.store.stage_bytes(content, "text/plain")

    def _reopen(self) -> None:
        self.connection.close()
        self.connection = connect_database(self.workspace / "nana.db")
        self.reader = ArtifactReader(self.connection, self.store)

    def test_staged_artifact_event_and_outbox_commit_atomically(self) -> None:
        artifact_id = str(uuid4())
        staged = self._stage()

        event_id = self._service().record_staged(
            artifact_id,
            staged,
            retention={"class": "default"},
        )

        artifact = self.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        event = self.connection.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        outbox = self.connection.execute(
            "SELECT * FROM outbox_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        self.assertEqual(artifact["state"], "staged")
        self.assertEqual(artifact["temp_ref"], staged.temp_ref)
        self.assertEqual(artifact["blob_hash"], staged.blob_hash)
        self.assertEqual(int(artifact["size"]), staged.size)
        self.assertEqual(event["type"], "artifact.staged")
        self.assertEqual(int(event["aggregate_version"]), 1)
        self.assertEqual(
            json.loads(event["payload_json"]),
            {
                "artifact_id": artifact_id,
                "blob_hash": staged.blob_hash,
                "media_type": staged.media_type,
                "size": staged.size,
                "state": "staged",
                "temp_ref": staged.temp_ref,
            },
        )
        self.assertIsNotNone(outbox)
        with self.assertRaises(ArtifactNotAvailableError):
            self.reader.read_bytes(artifact_id)

    def test_staged_outbox_failure_rolls_back_artifact_and_event(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER fail_all_outbox
            BEFORE INSERT ON outbox_events
            BEGIN
                SELECT RAISE(ABORT, 'injected outbox failure');
            END
            """
        )
        self.connection.commit()
        artifact_id = str(uuid4())
        staged = self._stage()

        with self.assertRaisesRegex(sqlite3.IntegrityError, "outbox failure"):
            self._service().record_staged(artifact_id, staged)

        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                (artifact_id,),
            ).fetchone()[0],
            0,
        )
        self.assertTrue(staged.partial_path.exists())

    def test_commit_time_failure_rolls_back_and_closes_transaction(self) -> None:
        self.connection.execute("PRAGMA defer_foreign_keys = ON")
        artifact_id = str(uuid4())
        staged = self._stage()

        with self.assertRaises(sqlite3.IntegrityError):
            self._service().record_staged(
                artifact_id,
                staged,
                producer_run_id=str(uuid4()),
            )

        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                (artifact_id,),
            ).fetchone()[0],
            0,
        )

    def test_crash_after_staged_transaction_keeps_partial_invisible(self) -> None:
        def checkpoint(name: str) -> None:
            if name == "staged_committed":
                raise InjectedCrash(name)

        artifact_id = str(uuid4())
        staged = self._stage()

        with self.assertRaisesRegex(InjectedCrash, "staged_committed"):
            self._service(checkpoint).commit(artifact_id, staged)

        self._reopen()
        row = self.connection.execute(
            "SELECT state, temp_ref FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        self.assertEqual((row["state"], row["temp_ref"]), ("staged", staged.temp_ref))
        self.assertTrue(staged.partial_path.exists())
        self.assertFalse(self.store.blob_path(staged.blob_hash).exists())
        with self.assertRaises(ArtifactNotAvailableError):
            self.reader.read_bytes(artifact_id)

    def test_crash_after_rename_keeps_final_blob_invisible(self) -> None:
        def checkpoint(name: str) -> None:
            if name == "blob_promoted":
                raise InjectedCrash(name)

        artifact_id = str(uuid4())
        staged = self._stage()

        with self.assertRaisesRegex(InjectedCrash, "blob_promoted"):
            self._service(checkpoint).commit(artifact_id, staged)

        self._reopen()
        row = self.connection.execute(
            "SELECT state, temp_ref FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        self.assertEqual((row["state"], row["temp_ref"]), ("staged", staged.temp_ref))
        self.assertFalse(staged.partial_path.exists())
        self.assertTrue(self.store.blob_path(staged.blob_hash).exists())
        with self.assertRaises(ArtifactNotAvailableError):
            self.reader.read_bytes(artifact_id)

    def test_rename_failure_keeps_first_transaction_and_partial(self) -> None:
        def failing_replace(source: Path, destination: Path) -> None:
            raise OSError("injected rename failure")

        store = ArtifactStore(self.workspace, replace=failing_replace)
        artifact_id = str(uuid4())
        staged = store.stage_bytes(b"rename failure", "text/plain")

        with self.assertRaisesRegex(OSError, "rename failure"):
            ArtifactCommitService(
                self.connection,
                store,
                now=lambda: NOW,
            ).commit(artifact_id, staged)

        self._reopen()
        row = self.connection.execute(
            "SELECT state, temp_ref FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        self.assertEqual((row["state"], row["temp_ref"]), ("staged", staged.temp_ref))
        self.assertTrue(staged.partial_path.exists())
        self.assertFalse(store.blob_path(staged.blob_hash).exists())
        with self.assertRaises(ArtifactNotAvailableError):
            ArtifactReader(self.connection, store).read_bytes(artifact_id)

    def test_final_blob_is_reverified_before_available_transaction(self) -> None:
        for failure_mode in ("missing", "corrupt"):
            with self.subTest(failure_mode=failure_mode):
                artifact_id = str(uuid4())
                staged = self._stage(f"final {failure_mode}".encode())
                final_path = self.store.blob_path(staged.blob_hash)

                def checkpoint(name: str) -> None:
                    if name != "blob_promoted":
                        return
                    if failure_mode == "missing":
                        final_path.unlink()
                    else:
                        final_path.write_bytes(b"corrupt after rename")

                with self.assertRaises(ArtifactIntegrityError):
                    self._service(checkpoint).commit(artifact_id, staged)

                self._reopen()
                row = self.connection.execute(
                    "SELECT state, temp_ref FROM artifacts WHERE id = ?",
                    (artifact_id,),
                ).fetchone()
                self.assertEqual(
                    (row["state"], row["temp_ref"]),
                    ("staged", staged.temp_ref),
                )
                self.assertEqual(
                    self.connection.execute(
                        "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                with self.assertRaises(ArtifactNotAvailableError):
                    self.reader.read_bytes(artifact_id)

    def test_available_outbox_failure_rolls_back_second_transaction(self) -> None:
        artifact_id = str(uuid4())
        staged = self._stage()
        service = self._service()
        staged_event_id = service.record_staged(artifact_id, staged)
        self.connection.execute(
            """
            CREATE TRIGGER fail_committed_outbox
            BEFORE INSERT ON outbox_events
            WHEN (
                SELECT type FROM events WHERE id = NEW.event_id
            ) = 'artifact.committed'
            BEGIN
                SELECT RAISE(ABORT, 'injected committed outbox failure');
            END
            """
        )
        self.connection.commit()

        with self.assertRaisesRegex(sqlite3.IntegrityError, "outbox failure"):
            service.promote_and_publish(artifact_id, staged)

        self._reopen()
        row = self.connection.execute(
            "SELECT state, temp_ref FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        self.assertEqual((row["state"], row["temp_ref"]), ("staged", staged.temp_ref))
        events = self.connection.execute(
            "SELECT id, type FROM events WHERE aggregate_id = ? ORDER BY id",
            (artifact_id,),
        ).fetchall()
        self.assertEqual(
            [(int(row["id"]), row["type"]) for row in events],
            [(staged_event_id, "artifact.staged")],
        )
        self.assertTrue(self.store.blob_path(staged.blob_hash).exists())
        with self.assertRaises(ArtifactNotAvailableError):
            self.reader.read_bytes(artifact_id)

    def test_successful_two_phase_commit_becomes_canonically_readable(self) -> None:
        artifact_id = str(uuid4())
        content = b"committed payload"
        staged = self._stage(content)

        result = self._service().commit(
            artifact_id,
            staged,
            license="CC0-1.0",
            retention={"class": "pinned"},
        )

        self._reopen()
        row = self.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        self.assertEqual(row["state"], "available")
        self.assertIsNone(row["temp_ref"])
        self.assertEqual(row["license"], "CC0-1.0")
        events = self.connection.execute(
            """
            SELECT id, aggregate_version, type
            FROM events
            WHERE aggregate_id = ?
            ORDER BY id
            """,
            (artifact_id,),
        ).fetchall()
        self.assertEqual(
            [
                (int(row["id"]), int(row["aggregate_version"]), row["type"])
                for row in events
            ],
            [
                (result.staged_event_id, 1, "artifact.staged"),
                (result.committed_event_id, 2, "artifact.committed"),
            ],
        )
        committed_payload = json.loads(
            self.connection.execute(
                "SELECT payload_json FROM events WHERE id = ?",
                (result.committed_event_id,),
            ).fetchone()["payload_json"]
        )
        self.assertEqual(
            committed_payload,
            {
                "artifact_id": artifact_id,
                "blob_hash": staged.blob_hash,
                "media_type": staged.media_type,
                "size": staged.size,
                "state": "available",
            },
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM outbox_events WHERE event_id IN (?, ?)",
                (result.staged_event_id, result.committed_event_id),
            ).fetchone()[0],
            2,
        )
        self.assertEqual(result.final_path, self.store.blob_path(staged.blob_hash))
        self.assertEqual(self.reader.read_bytes(artifact_id), content)

    def test_publish_requires_matching_canonical_staged_row(self) -> None:
        artifact_id = str(uuid4())
        staged = self._stage()

        with self.assertRaisesRegex(ArtifactNotAvailableError, "not staged"):
            self._service().promote_and_publish(artifact_id, staged)

        self.assertTrue(staged.partial_path.exists())
        self.assertFalse(self.store.blob_path(staged.blob_hash).exists())


if __name__ == "__main__":
    unittest.main()
