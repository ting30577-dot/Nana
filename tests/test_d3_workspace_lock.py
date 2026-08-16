"""D3-01 Workspace ownership lifecycle gate."""

from __future__ import annotations

import subprocess
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from nana_sidecar.storage.artifact_commits import ArtifactCommitService
from nana_sidecar.storage.artifacts import ArtifactStore
from nana_sidecar.storage.database import initialize_database
from nana_sidecar.storage.workspace_lock import WorkspaceLockError, WorkspaceRuntime


class WorkspaceLockLifecycleTests(unittest.TestCase):
    def test_lock_precedes_writable_open_and_reconcile_precedes_ready(self) -> None:
        events: list[str] = []

        class FakeConnection:
            def close(self) -> None:
                events.append("database.close")

        class RecordingLock:
            def acquire(self) -> None:
                events.append("lock.acquire")

            def release(self) -> None:
                events.append("lock.release")

        runtime = WorkspaceRuntime("nana.db")
        runtime._reconcile_artifacts = lambda _c: events.append("reconcile")
        runtime.lock = RecordingLock()
        with patch(
            "nana_sidecar.storage.workspace_lock.initialize_database",
            side_effect=lambda _path: events.append("database.open") or FakeConnection(),
        ):
            runtime.start()
        self.assertEqual(
            events,
            ["lock.acquire", "database.open", "reconcile"],
        )
        self.assertEqual(runtime.state, "ready")
        runtime.close()
        self.assertEqual(
            events,
            [
                "lock.acquire",
                "database.open",
                "reconcile",
                "database.close",
                "lock.release",
            ],
        )

    def test_lock_reconcile_ready_close_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events: list[str] = []

            class RecordingRuntime(WorkspaceRuntime):
                def start(self):
                    events.append("before_start")
                    result = super().start()
                    events.append("after_ready")
                    return result

            runtime = RecordingRuntime(root / "nana.db")
            runtime._reconcile_artifacts = lambda connection: events.append(
                f"reconcile:{connection.in_transaction}"
            )
            runtime.start()
            self.assertEqual(runtime.state, "ready")
            self.assertEqual(events, ["before_start", "reconcile:False", "after_ready"])
            runtime.close()
            self.assertEqual(runtime.state, "closed")
            self.assertIsNone(runtime.connection)

    def test_second_process_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / "workspace.owner.lock"
            runtime = WorkspaceRuntime(root / "nana.db")
            runtime.start()
            script = (
                "from nana_sidecar.storage.workspace_lock import WorkspaceLock, WorkspaceLockError; "
                f"lock=WorkspaceLock({str(lock_path)!r}); "
                "\ntry:\n lock.acquire()\nexcept WorkspaceLockError:\n raise SystemExit(0)\nelse:\n raise SystemExit(7)"
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            runtime.close()

    def test_start_failure_releases_lock_for_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = 0

            def fail_once(_connection) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("reconcile failure")

            runtime = WorkspaceRuntime(root / "nana.db")
            runtime._reconcile_artifacts = fail_once
            with self.assertRaisesRegex(RuntimeError, "reconcile failure"):
                runtime.start()
            self.assertEqual(runtime.state, "closed")
            restarted = WorkspaceRuntime(root / "nana.db")
            restarted._reconcile_artifacts = fail_once
            restarted.start()
            self.assertEqual(restarted.state, "ready")
            restarted.close()

    def test_database_close_failure_retains_workspace_lock(self) -> None:
        events: list[str] = []

        class FailingConnection:
            def close(self) -> None:
                events.append("database.close.failed")
                raise RuntimeError("close failed")

        class RecordingLock:
            def acquire(self) -> None:
                events.append("lock.acquire")

            def release(self) -> None:
                events.append("lock.release")

        runtime = WorkspaceRuntime("nana.db")
        runtime._reconcile_artifacts = lambda _connection: None
        runtime.lock = RecordingLock()
        with patch(
            "nana_sidecar.storage.workspace_lock.initialize_database",
            return_value=FailingConnection(),
        ):
            runtime.start()
        with self.assertRaisesRegex(RuntimeError, "close failed"):
            runtime.close()
        self.assertEqual(runtime.state, "close_failed")
        self.assertEqual(events, ["lock.acquire", "database.close.failed"])

    def test_lock_release_failure_never_claims_closed(self) -> None:
        events: list[str] = []

        class FakeConnection:
            def close(self) -> None:
                events.append("database.close")

        class FailingReleaseLock:
            is_held = True

            def acquire(self) -> None:
                events.append("lock.acquire")

            def release(self) -> None:
                events.append("lock.release.failed")
                raise RuntimeError("release failed")

        runtime = WorkspaceRuntime("nana.db")
        runtime._reconcile_artifacts = lambda _connection: None
        runtime.lock = FailingReleaseLock()
        with patch(
            "nana_sidecar.storage.workspace_lock.initialize_database",
            return_value=FakeConnection(),
        ):
            runtime.start()
        with self.assertRaisesRegex(RuntimeError, "release failed"):
            runtime.close()
        self.assertEqual(runtime.state, "lock_release_failed")
        self.assertIsNone(runtime.connection)
        self.assertEqual(
            events,
            ["lock.acquire", "database.close", "lock.release.failed"],
        )

    def test_startup_cleanup_close_failure_retains_workspace_lock(self) -> None:
        events: list[str] = []

        class FailingConnection:
            def close(self) -> None:
                events.append("database.close.failed")
                raise RuntimeError("close failed")

        class RecordingLock:
            is_held = True

            def acquire(self) -> None:
                events.append("lock.acquire")

            def release(self) -> None:
                events.append("lock.release")

        def fail_reconcile(_connection) -> None:
            raise RuntimeError("reconcile failed")

        runtime = WorkspaceRuntime("nana.db")
        runtime._reconcile_artifacts = fail_reconcile
        runtime.lock = RecordingLock()
        with patch(
            "nana_sidecar.storage.workspace_lock.initialize_database",
            return_value=FailingConnection(),
        ):
            with self.assertRaisesRegex(
                WorkspaceLockError,
                "ownership is retained",
            ):
                runtime.start()
        self.assertEqual(runtime.state, "startup_close_failed")
        self.assertEqual(events, ["lock.acquire", "database.close.failed"])

    def test_quiesce_failure_retains_database_and_lock(self) -> None:
        events: list[str] = []

        class FakeConnection:
            def close(self) -> None:
                events.append("database.close")

        class RecordingLock:
            is_held = True

            def acquire(self) -> None:
                events.append("lock.acquire")

            def release(self) -> None:
                events.append("lock.release")

        def writers_active() -> None:
            raise RuntimeError("writers active")

        runtime = WorkspaceRuntime(
            "nana.db",
            quiesce_writers=writers_active,
        )
        runtime._reconcile_artifacts = lambda _connection: None
        runtime.lock = RecordingLock()
        with patch(
            "nana_sidecar.storage.workspace_lock.initialize_database",
            return_value=FakeConnection(),
        ):
            runtime.start()
        with self.assertRaisesRegex(RuntimeError, "writers active"):
            runtime.close()
        self.assertEqual(runtime.state, "drain_failed")
        self.assertIsNotNone(runtime.connection)
        self.assertEqual(events, ["lock.acquire"])

    def test_default_runtime_runs_real_artifact_reconciliation_before_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "nana.db"
            store = ArtifactStore(root)
            staged = store.stage_bytes(b"recover me", "text/plain")
            artifact_id = str(uuid4())
            connection = initialize_database(database_path)
            ArtifactCommitService(connection, store).record_staged(
                artifact_id,
                staged,
            )
            connection.close()

            runtime = WorkspaceRuntime(database_path)
            runtime.start()
            self.assertEqual(runtime.state, "ready")
            self.assertIsNotNone(runtime.reconciliation_report)
            state = runtime.connection.execute(
                "SELECT state FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()[0]
            self.assertEqual(state, "available")
            event = runtime.connection.execute(
                "SELECT type FROM events WHERE aggregate_id = ? ORDER BY id DESC",
                (artifact_id,),
            ).fetchone()[0]
            self.assertEqual(event, "artifact.reconciled")
            runtime.close()

    def test_real_reconciler_failure_never_reaches_ready_and_restart_converges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "nana.db"
            store = ArtifactStore(root)
            staged = store.stage_bytes(b"recover after failure", "text/plain")
            artifact_id = str(uuid4())
            connection = initialize_database(database_path)
            ArtifactCommitService(connection, store).record_staged(
                artifact_id,
                staged,
            )
            connection.close()

            failed = WorkspaceRuntime(database_path)
            with patch.object(
                ArtifactStore,
                "promote",
                side_effect=OSError("promote failed"),
            ):
                with self.assertRaisesRegex(OSError, "promote failed"):
                    failed.start()
            self.assertEqual(failed.state, "closed")
            self.assertIsNone(failed.connection)

            recovered = WorkspaceRuntime(database_path)
            recovered.start()
            state = recovered.connection.execute(
                "SELECT state FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()[0]
            self.assertEqual(state, "available")
            recovered.close()

    def test_schema_v7_has_no_persisted_workspace_lock_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = WorkspaceRuntime(Path(directory) / "nana.db")
            runtime.start()
            names = {
                str(row[0]).casefold()
                for row in runtime.connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type IN ('table', 'view')"
                )
            }
            self.assertFalse(
                any("workspace" in name and "lock" in name for name in names)
            )
            columns = {
                str(row[1]).casefold()
                for table in names
                for row in runtime.connection.execute(
                    f'PRAGMA table_info("{table}")'
                )
            }
            forbidden_fragments = {"workspace_lock", "lock_owner", "owner_lock"}
            self.assertFalse(
                any(
                    fragment in column
                    for column in columns
                    for fragment in forbidden_fragments
                )
            )
            self.assertEqual(
                runtime.connection.execute("PRAGMA user_version").fetchone()[0],
                7,
            )
            runtime.close()

    def test_lock_symlink_resolving_outside_workspace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.lock"
            outside.touch()
            workspace = root / "workspace"
            workspace.mkdir()
            link = workspace / "workspace.owner.lock"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaisesRegex(
                WorkspaceLockError,
                "resolve beside",
            ):
                WorkspaceRuntime(workspace / "nana.db")

    def test_lock_identity_outside_database_parent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside" / "workspace.owner.lock"
            with patch(
                "nana_sidecar.storage.workspace_lock.WorkspaceLock"
            ) as lock_type:
                lock_type.return_value.path = outside
                with self.assertRaisesRegex(
                    WorkspaceLockError,
                    "resolve beside",
                ):
                    WorkspaceRuntime(root / "workspace" / "nana.db")

    def test_database_reparse_identity_is_rejected_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "nana.db"
            database_path.touch()
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaisesRegex(
                    WorkspaceLockError,
                    "database must not be a reparse point",
                ):
                    WorkspaceRuntime(database_path)

    def test_process_crash_releases_os_lock_for_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (
                "import time; "
                "from nana_sidecar.storage.workspace_lock import WorkspaceRuntime; "
                f"runtime=WorkspaceRuntime({str(root / 'nana.db')!r}); "
                "runtime.start(); "
                "print('READY', flush=True); time.sleep(60)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(process.stdout.readline().strip(), "READY")
                contender = WorkspaceRuntime(root / "nana.db")
                with self.assertRaises(WorkspaceLockError):
                    contender.start()
                process.kill()
                _stdout, child_stderr = process.communicate(timeout=5)
                deadline = time.monotonic() + 5
                last_error: Exception | None = None
                while True:
                    recovered = WorkspaceRuntime(root / "nana.db")
                    try:
                        recovered.start()
                        break
                    except sqlite3.OperationalError as exc:
                        last_error = exc
                        if time.monotonic() >= deadline:
                            self.fail(
                                "crashed owner did not release SQLite before restart; "
                                f"child exit={process.returncode}, "
                                f"child stderr={child_stderr[-4000:]!r}, "
                                f"last error={last_error!r}"
                            )
                        time.sleep(0.02)
                self.assertEqual(recovered.state, "ready")
                recovered.close()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main()
