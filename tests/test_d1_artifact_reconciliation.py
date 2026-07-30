"""D1-04 gate for all six Artifact reconciliation branches."""

from __future__ import annotations

import math
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from nana_sidecar.storage import connect_database, initialize_database
from nana_sidecar.storage.artifact_commits import (
    ArtifactCommitService,
    ArtifactReader,
)
from nana_sidecar.storage.artifact_reconciliation import ArtifactReconciler
from nana_sidecar.storage.artifacts import (
    ArtifactNotAvailableError,
    ArtifactStore,
)


NOW = "2026-07-29T00:00:00Z"
FAULT_RUNS = 20


class InjectedReconciliationCrash(RuntimeError):
    pass


class CrashOnce:
    def __init__(self, target: str) -> None:
        self.target = target
        self.fired = False

    def __call__(self, checkpoint: str) -> None:
        if checkpoint == self.target and not self.fired:
            self.fired = True
            raise InjectedReconciliationCrash(checkpoint)


class D1ArtifactReconciliationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _runtime(self, branch: str, iteration: int):
        workspace = self.root / branch / f"case-{iteration}"
        database_path = workspace / "nana.db"
        connection = initialize_database(database_path)
        store = ArtifactStore(workspace)
        return workspace, database_path, connection, store

    def _commit_service(self, connection, store):
        return ArtifactCommitService(
            connection,
            store,
            now=lambda: NOW,
        )

    def _reconciler(self, connection, store, checkpoint=None):
        return ArtifactReconciler(
            connection,
            store,
            now=lambda: 1_000_000.0,
            grace_seconds=0,
            checkpoint=checkpoint,
        )

    def _assert_unreadable(self, connection, store, artifact_id: str) -> None:
        with self.assertRaises(ArtifactNotAvailableError):
            ArtifactReader(connection, store).read_bytes(artifact_id)

    def _reopen(self, connection, database_path: Path):
        connection.close()
        return connect_database(database_path)

    def test_partial_only_branch_fault_injection_20_times(self) -> None:
        for iteration in range(FAULT_RUNS):
            with self.subTest(iteration=iteration):
                _, database_path, connection, store = self._runtime(
                    "partial-only",
                    iteration,
                )
                staged = store.stage_bytes(
                    f"partial-{iteration}".encode(),
                    "text/plain",
                )
                os.utime(staged.partial_path, (0, 0))
                crash = CrashOnce("partial_quarantined")

                with self.assertRaisesRegex(
                    InjectedReconciliationCrash,
                    "partial_quarantined",
                ):
                    self._reconciler(connection, store, crash).scan()

                connection = self._reopen(connection, database_path)
                self._assert_unreadable(connection, store, str(uuid4()))
                self._reconciler(connection, store).scan()
                second = self._reconciler(connection, store).scan()
                self.assertEqual(second.actions, ())
                self.assertTrue(crash.fired)
                self.assertFalse(staged.partial_path.exists())
                self.assertEqual(
                    len(list(store.partial_quarantine_root.glob("*.partial"))),
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
                    0,
                )
                connection.close()

    def test_staged_partial_branch_fault_injection_20_times(self) -> None:
        for iteration in range(FAULT_RUNS):
            with self.subTest(iteration=iteration):
                _, database_path, connection, store = self._runtime(
                    "staged-partial",
                    iteration,
                )
                artifact_id = str(uuid4())
                content = f"staged-partial-{iteration}".encode()
                staged = store.stage_bytes(content, "text/plain")
                self._commit_service(connection, store).record_staged(
                    artifact_id,
                    staged,
                )
                crash = CrashOnce("staged_partial_promoted")

                with self.assertRaisesRegex(
                    InjectedReconciliationCrash,
                    "staged_partial_promoted",
                ):
                    self._reconciler(connection, store, crash).scan()

                connection = self._reopen(connection, database_path)
                self._assert_unreadable(connection, store, artifact_id)
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "staged",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertTrue(store.blob_path(staged.blob_hash).exists())
                self._reconciler(connection, store).scan()
                second = self._reconciler(connection, store).scan()
                self.assertEqual(second.actions, ())
                self.assertEqual(
                    ArtifactReader(connection, store).read_bytes(artifact_id),
                    content,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "available",
                )
                event_types = [
                    row["type"]
                    for row in connection.execute(
                        "SELECT type FROM events WHERE aggregate_id = ? ORDER BY id",
                        (artifact_id,),
                    )
                ]
                self.assertEqual(
                    event_types,
                    ["artifact.staged", "artifact.reconciled"],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    2,
                )
                self.assertTrue(crash.fired)
                connection.close()

    def test_staged_final_branch_fault_injection_20_times(self) -> None:
        for iteration in range(FAULT_RUNS):
            with self.subTest(iteration=iteration):
                _, database_path, connection, store = self._runtime(
                    "staged-final",
                    iteration,
                )
                artifact_id = str(uuid4())
                content = f"staged-final-{iteration}".encode()
                staged = store.stage_bytes(content, "text/plain")
                self._commit_service(connection, store).record_staged(
                    artifact_id,
                    staged,
                )
                store.promote(staged)
                crash = CrashOnce("staged_final_ready")

                with self.assertRaisesRegex(
                    InjectedReconciliationCrash,
                    "staged_final_ready",
                ):
                    self._reconciler(connection, store, crash).scan()

                connection = self._reopen(connection, database_path)
                self._assert_unreadable(connection, store, artifact_id)
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "staged",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                self._reconciler(connection, store).scan()
                second = self._reconciler(connection, store).scan()
                self.assertEqual(second.actions, ())
                self.assertEqual(
                    ArtifactReader(connection, store).read_bytes(artifact_id),
                    content,
                )
                event_types = [
                    row["type"]
                    for row in connection.execute(
                        "SELECT type FROM events WHERE aggregate_id = ? ORDER BY id",
                        (artifact_id,),
                    )
                ]
                self.assertEqual(
                    event_types,
                    ["artifact.staged", "artifact.reconciled"],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    2,
                )
                self.assertTrue(crash.fired)
                connection.close()

    def test_staged_missing_or_corrupt_branch_fault_injection_20_times(self) -> None:
        for iteration in range(FAULT_RUNS):
            with self.subTest(iteration=iteration):
                _, database_path, connection, store = self._runtime(
                    "staged-failed",
                    iteration,
                )
                artifact_id = str(uuid4())
                staged = store.stage_bytes(
                    f"staged-failed-{iteration}".encode(),
                    "text/plain",
                )
                self._commit_service(connection, store).record_staged(
                    artifact_id,
                    staged,
                )
                staged.partial_path.write_bytes(b"corrupt partial")
                crash = CrashOnce("staged_failed_ready")

                with self.assertRaisesRegex(
                    InjectedReconciliationCrash,
                    "staged_failed_ready",
                ):
                    self._reconciler(connection, store, crash).scan()

                connection = self._reopen(connection, database_path)
                self._assert_unreadable(connection, store, artifact_id)
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "staged",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    1,
                )
                self._reconciler(connection, store).scan()
                second = self._reconciler(connection, store).scan()
                self.assertEqual(second.actions, ())
                self._assert_unreadable(connection, store, artifact_id)
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "failed",
                )
                event_types = [
                    row["type"]
                    for row in connection.execute(
                        "SELECT type FROM events WHERE aggregate_id = ? ORDER BY id",
                        (artifact_id,),
                    )
                ]
                self.assertEqual(
                    event_types,
                    ["artifact.staged", "artifact.reconciled"],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    2,
                )
                self.assertTrue(crash.fired)
                connection.close()

    def test_available_missing_branch_fault_injection_20_times(self) -> None:
        for iteration in range(FAULT_RUNS):
            with self.subTest(iteration=iteration):
                _, database_path, connection, store = self._runtime(
                    "available-missing",
                    iteration,
                )
                artifact_id = str(uuid4())
                staged = store.stage_bytes(
                    f"available-missing-{iteration}".encode(),
                    "text/plain",
                )
                self._commit_service(connection, store).commit(
                    artifact_id,
                    staged,
                )
                store.blob_path(staged.blob_hash).unlink()
                crash = CrashOnce("available_corrupt_ready")

                with self.assertRaisesRegex(
                    InjectedReconciliationCrash,
                    "available_corrupt_ready",
                ):
                    self._reconciler(connection, store, crash).scan()

                connection = self._reopen(connection, database_path)
                self._assert_unreadable(connection, store, artifact_id)
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "available",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                        (artifact_id,),
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    2,
                )
                self._reconciler(connection, store).scan()
                second = self._reconciler(connection, store).scan()
                self.assertEqual(second.actions, ())
                self._assert_unreadable(connection, store, artifact_id)
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM artifacts WHERE id = ?",
                        (artifact_id,),
                    ).fetchone()["state"],
                    "corrupt",
                )
                event_types = [
                    row["type"]
                    for row in connection.execute(
                        "SELECT type FROM events WHERE aggregate_id = ? ORDER BY id",
                        (artifact_id,),
                    )
                ]
                self.assertEqual(
                    event_types,
                    [
                        "artifact.staged",
                        "artifact.committed",
                        "artifact.reconciled",
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events AS outbox
                        JOIN events AS event ON event.id = outbox.event_id
                        WHERE event.aggregate_id = ?
                        """,
                        (artifact_id,),
                    ).fetchone()[0],
                    3,
                )
                self.assertTrue(crash.fired)
                connection.close()

    def test_shared_hash_recovery_is_independent_of_artifact_id_order(self) -> None:
        _, _, connection, store = self._runtime("shared-hash", 0)
        self.addCleanup(connection.close)
        available_id = "00000000-0000-0000-0000-000000000001"
        staged_id = "00000000-0000-0000-0000-000000000002"
        content = b"shared content"
        available_stage = store.stage_bytes(content, "text/plain")
        self._commit_service(connection, store).commit(
            available_id,
            available_stage,
        )
        staged = store.stage_bytes(content, "text/plain")
        self._commit_service(connection, store).record_staged(
            staged_id,
            staged,
        )
        store.blob_path(staged.blob_hash).unlink()

        self._reconciler(connection, store).scan()

        states = {
            row["id"]: row["state"]
            for row in connection.execute("SELECT id, state FROM artifacts")
        }
        self.assertEqual(
            states,
            {
                available_id: "available",
                staged_id: "available",
            },
        )
        self.assertEqual(
            ArtifactReader(connection, store).read_bytes(available_id),
            content,
        )
        self.assertEqual(
            ArtifactReader(connection, store).read_bytes(staged_id),
            content,
        )
        self.assertEqual(self._reconciler(connection, store).scan().actions, ())
        connection.close()

    def test_staged_final_quarantines_corrupt_duplicate_partial_in_one_scan(
        self,
    ) -> None:
        _, _, connection, store = self._runtime("duplicate-partial", 0)
        self.addCleanup(connection.close)
        artifact_id = str(uuid4())
        content = b"valid final and corrupt duplicate partial"
        staged = store.stage_bytes(content, "text/plain")
        self._commit_service(connection, store).record_staged(
            artifact_id,
            staged,
        )
        final_path = store.blob_path(staged.blob_hash)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(content)
        staged.partial_path.write_bytes(b"corrupt")

        first = self._reconciler(connection, store).scan()

        self.assertIn(
            "duplicate_partial_quarantined",
            {action.kind for action in first.actions},
        )
        self.assertFalse(staged.partial_path.exists())
        self.assertEqual(
            len(list(store.partial_quarantine_root.glob("*.partial"))),
            1,
        )
        self.assertEqual(self._reconciler(connection, store).scan().actions, ())
        self.assertEqual(
            ArtifactReader(connection, store).read_bytes(artifact_id),
            content,
        )
        connection.close()

    def test_valid_partial_replaces_corrupt_final_before_availability(
        self,
    ) -> None:
        _, _, connection, store = self._runtime("corrupt-final-repair", 0)
        self.addCleanup(connection.close)
        artifact_id = str(uuid4())
        content = b"valid staged content"
        staged = store.stage_bytes(content, "text/plain")
        self._commit_service(connection, store).record_staged(
            artifact_id,
            staged,
        )
        final_path = store.blob_path(staged.blob_hash)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(b"corrupt final")

        report = self._reconciler(connection, store).scan()

        self.assertEqual(
            {action.kind for action in report.actions},
            {
                "corrupt_final_quarantined",
                "staged_partial_promoted",
                "staged_partial_available",
            },
        )
        self.assertEqual(
            ArtifactReader(connection, store).read_bytes(artifact_id),
            content,
        )
        self.assertEqual(
            len(list(store.corrupt_quarantine_root.glob("*"))),
            1,
        )
        self.assertEqual(self._reconciler(connection, store).scan().actions, ())
        connection.close()

    def test_available_corrupt_blob_is_never_returned(self) -> None:
        _, _, connection, store = self._runtime("available-corrupt", 0)
        self.addCleanup(connection.close)
        artifact_id = str(uuid4())
        staged = store.stage_bytes(b"valid content", "text/plain")
        self._commit_service(connection, store).commit(artifact_id, staged)
        store.blob_path(staged.blob_hash).write_bytes(b"corrupt")

        report = self._reconciler(connection, store).scan()

        self.assertEqual(
            tuple(action.kind for action in report.actions),
            ("available_corrupt",),
        )
        self._assert_unreadable(connection, store, artifact_id)
        self.assertEqual(
            connection.execute(
                "SELECT state FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()["state"],
            "corrupt",
        )
        self.assertEqual(self._reconciler(connection, store).scan().actions, ())
        connection.close()

    def test_quarantine_volume_identity_uses_entry_directories(self) -> None:
        workspace = self.root / "quarantine-volume"

        def volume_id(path: Path) -> str:
            candidate = Path(path)
            if candidate.parent.name == ".staging":
                return "symlink-target-volume"
            return "workspace-volume"

        store = ArtifactStore(workspace, volume_id=volume_id)
        database_path = workspace / "nana.db"
        connection = initialize_database(database_path)
        self.addCleanup(connection.close)
        staged = store.stage_bytes(b"old partial", "text/plain")
        os.utime(staged.partial_path, (0, 0))

        report = self._reconciler(connection, store).scan()

        self.assertEqual(
            tuple(action.kind for action in report.actions),
            ("partial_quarantined",),
        )
        self.assertFalse(staged.partial_path.exists())
        connection.close()

    def test_fresh_partial_waits_for_grace_and_quarantine_failure_retries(
        self,
    ) -> None:
        workspace = self.root / "partial-grace-retry"
        database_path = workspace / "nana.db"
        connection = initialize_database(database_path)

        def fail_replace(source: Path, target: Path) -> None:
            raise OSError("injected quarantine rename failure")

        failing_store = ArtifactStore(workspace, replace=fail_replace)
        staged = failing_store.stage_bytes(b"fresh partial", "text/plain")
        os.utime(staged.partial_path, (950, 950))
        fresh = ArtifactReconciler(
            connection,
            failing_store,
            now=lambda: 1_000.0,
            grace_seconds=100,
        ).scan()
        self.assertEqual(fresh.actions, ())
        self.assertTrue(staged.partial_path.exists())

        os.utime(staged.partial_path, (0, 0))
        with self.assertRaisesRegex(
            OSError,
            "injected quarantine rename failure",
        ):
            self._reconciler(connection, failing_store).scan()
        self.assertTrue(staged.partial_path.exists())

        recovered_store = ArtifactStore(workspace)
        recovered = self._reconciler(connection, recovered_store).scan()
        self.assertEqual(
            tuple(action.kind for action in recovered.actions),
            ("partial_quarantined",),
        )
        self.assertEqual(
            self._reconciler(connection, recovered_store).scan().actions,
            (),
        )
        connection.close()

    def test_reconciliation_grace_must_be_finite_non_boolean_number(self) -> None:
        _, _, connection, store = self._runtime("invalid-grace", 0)
        try:
            for invalid in (math.nan, math.inf, -math.inf, True):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "grace_seconds"):
                        ArtifactReconciler(
                            connection,
                            store,
                            grace_seconds=invalid,
                        )
        finally:
            connection.close()

    def test_orphan_final_branch_fault_injection_20_times(self) -> None:
        for iteration in range(FAULT_RUNS):
            with self.subTest(iteration=iteration):
                _, database_path, connection, store = self._runtime(
                    "orphan-final",
                    iteration,
                )
                staged = store.stage_bytes(
                    f"orphan-final-{iteration}".encode(),
                    "application/octet-stream",
                )
                final_path = store.promote(staged)
                crash = CrashOnce("orphan_blob_quarantined")

                with self.assertRaisesRegex(
                    InjectedReconciliationCrash,
                    "orphan_blob_quarantined",
                ):
                    self._reconciler(connection, store, crash).scan()

                connection = self._reopen(connection, database_path)
                self._assert_unreadable(connection, store, str(uuid4()))
                self._reconciler(connection, store).scan()
                second = self._reconciler(connection, store).scan()
                self.assertEqual(second.actions, ())
                self.assertFalse(final_path.exists())
                self.assertEqual(
                    len(list(store.orphan_quarantine_root.glob("*"))),
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
                    0,
                )
                self.assertTrue(crash.fired)
                connection.close()


if __name__ == "__main__":
    unittest.main()
