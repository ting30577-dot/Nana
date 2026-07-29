"""D0 SQLite migration, schema, and ceiling tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from nana_sidecar.storage import (
    IncompatibleDatabaseError,
    SchemaTooNewError,
    connect_database,
    initialize_database,
    plan_database_migrations,
)
from nana_sidecar.storage.database import _apply_migration
from nana_sidecar.storage.migrations import Migration
from nana_sidecar.contracts.domain import EventType


EXPECTED_TABLES = {
    "schema_metadata",
    "migration_history",
    "workspaces",
    "projects",
    "inquiries",
    "plans",
    "runs",
    "artifacts",
    "actions",
    "policy_grants",
    "approvals",
    "action_receipts",
    "events",
    "outbox_events",
    "command_log",
    "resources",
    "locators",
    "claims",
    "evidence",
    "hypotheses",
    "methods",
    "findings",
    "decisions",
    "relations",
}


def event_probe_shape(event_type: EventType) -> tuple[str, str, str]:
    aggregate_type = "contract_probe"
    aggregate_id = "event-type-registry"
    payload: dict[str, object] = {}
    if event_type is EventType.ARTIFACT_STAGED:
        aggregate_type = "artifact"
        payload = {
            "artifact_id": aggregate_id,
            "state": "staged",
            "temp_ref": "staging/probe.partial",
            "blob_hash": "sha256:" + "a" * 64,
            "size": 7,
            "media_type": "text/plain",
        }
    elif event_type is EventType.ARTIFACT_COMMITTED:
        aggregate_type = "artifact"
        payload = {
            "artifact_id": aggregate_id,
            "state": "available",
            "blob_hash": "sha256:" + "a" * 64,
            "size": 7,
            "media_type": "text/plain",
        }
    elif event_type is EventType.ARTIFACT_RECONCILED:
        aggregate_type = "artifact"
        payload = {
            "artifact_id": aggregate_id,
            "previous_state": "staged",
            "state": "available",
            "reason_code": "complete_staged_commit",
        }
    return aggregate_type, aggregate_id, json.dumps(payload)


class VNextStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace" / "nana-vnext.db"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_dry_run_plans_0001_without_creating_files(self) -> None:
        plan = plan_database_migrations(self.path)

        self.assertEqual(plan.current_version, 0)
        self.assertEqual(plan.target_version, 1)
        self.assertEqual([step.name for step in plan.steps], ["0001_contract_kernel"])
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.parent.exists())

    def test_initialize_creates_complete_vnext_schema_in_wal_mode(self) -> None:
        connection = initialize_database(self.path)
        try:
            tables = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            journal_mode = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).lower()
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            history = connection.execute(
                "SELECT version, name, contract_hash FROM migration_history"
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual(tables, EXPECTED_TABLES)
        self.assertEqual(journal_mode, "wal")
        self.assertEqual(version, 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(str(history[0]["name"]), "0001_contract_kernel")
        self.assertRegex(str(history[0]["contract_hash"]), r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(
            {"problems", "research_threads", "research_sources"} & tables
        )

    def test_reopen_is_idempotent_and_has_no_pending_migration(self) -> None:
        initialize_database(self.path).close()
        initialize_database(self.path).close()
        connection = connect_database(self.path)
        try:
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM migration_history"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        self.assertEqual(count, 1)
        self.assertEqual(plan_database_migrations(self.path).steps, ())

    def test_empty_uninitialized_database_is_not_a_connectable_workspace(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.touch()
        with self.assertRaisesRegex(IncompatibleDatabaseError, "not initialized"):
            connect_database(self.path)

    def test_higher_schema_is_refused_before_writes(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA user_version = 2")
        connection.close()
        with self.assertRaisesRegex(SchemaTooNewError, "exceeds read ceiling"):
            initialize_database(self.path)

    def test_legacy_or_unknown_database_is_never_extended(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        connection.execute("CREATE TABLE problems (id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            IncompatibleDatabaseError, "non-empty unversioned"
        ):
            initialize_database(self.path)
        connection = sqlite3.connect(self.path)
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()
        self.assertIn("problems", tables)
        self.assertNotIn("projects", tables)

    def test_tampered_migration_hash_is_refused(self) -> None:
        connection = initialize_database(self.path)
        with connection:
            connection.execute(
                "UPDATE migration_history SET contract_hash = ? WHERE version = 1",
                ("sha256:" + "0" * 64,),
            )
        connection.close()
        with self.assertRaisesRegex(IncompatibleDatabaseError, "hash mismatch"):
            connect_database(self.path)

    def test_failed_migration_rolls_back_its_partial_schema(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        broken = Migration(
            version=1,
            name="broken",
            sql="CREATE TABLE should_rollback(id INTEGER); INVALID SQL;",
            contract_hash="sha256:" + "0" * 64,
        )
        with self.assertRaises(sqlite3.Error):
            _apply_migration(connection, broken)
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()
        self.assertNotIn("should_rollback", tables)

    def test_canonical_relationships_use_restrict_delete(self) -> None:
        connection = initialize_database(self.path)
        try:
            with connection:
                connection.execute(
                    "INSERT INTO workspaces VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "workspace-1",
                        1,
                        "workspace",
                        json.dumps({}),
                        "active",
                        1,
                        "2026-07-29T00:00:00Z",
                    ),
                )
                connection.execute(
                    "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "project-1",
                        "workspace-1",
                        "Sliding-window boundary",
                        "active",
                        "public",
                        1,
                        "2026-07-29T00:00:00Z",
                    ),
                )
                connection.execute(
                    "INSERT INTO inquiries VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "inquiry-1",
                        "project-1",
                        "Why does the window require non-negative input?",
                        "Run the locked deterministic test.",
                        "draft",
                        1,
                        "2026-07-29T00:00:00Z",
                    ),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(
                        "DELETE FROM projects WHERE id = ?", ("project-1",)
                    )
        finally:
            connection.close()

    def test_event_requires_closed_type_and_exactly_one_payload(self) -> None:
        connection = initialize_database(self.path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(
                        """
                        INSERT INTO events (
                            aggregate_type, aggregate_id, aggregate_version,
                            actor_json, type, payload_json, occurred_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "project",
                            "project-1",
                            1,
                            "{}",
                            "made.up",
                            "{}",
                            "2026-07-29T00:00:00Z",
                        ),
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(
                        """
                        INSERT INTO events (
                            aggregate_type, aggregate_id, aggregate_version,
                            actor_json, type, occurred_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "project",
                            "project-1",
                            1,
                            "{}",
                            "project.created",
                            "2026-07-29T00:00:00Z",
                        ),
                    )
        finally:
            connection.close()

    def test_every_domain_event_type_is_accepted_by_storage_contract(self) -> None:
        connection = initialize_database(self.path)
        try:
            with connection:
                for version, event_type in enumerate(EventType, start=1):
                    aggregate_type, aggregate_id, payload_json = (
                        event_probe_shape(event_type)
                    )
                    connection.execute(
                        """
                        INSERT INTO events (
                            aggregate_type, aggregate_id, aggregate_version,
                            actor_json, type, payload_json, occurred_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            aggregate_type,
                            aggregate_id,
                            version,
                            '{"kind":"system"}',
                            event_type.value,
                            payload_json,
                            "2026-07-29T00:00:00Z",
                        ),
                    )
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM events"
                ).fetchone()[0]
            )
            self.assertEqual(count, len(EventType))
        finally:
            connection.close()

    def test_artifact_staging_and_event_payload_invariants(self) -> None:
        connection = initialize_database(self.path)
        artifact_id = "artifact-contract-probe"
        blob_hash = "sha256:" + "a" * 64
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(
                        """
                        INSERT INTO artifacts (
                            id, media_type, blob_hash, size, state,
                            retention_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "missing-temp-ref",
                            "text/plain",
                            blob_hash,
                            7,
                            "staged",
                            "{}",
                            "2026-07-29T00:00:00Z",
                        ),
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(
                        """
                        INSERT INTO artifacts (
                            id, media_type, blob_hash, size, state, temp_ref,
                            retention_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "available-with-temp-ref",
                            "text/plain",
                            blob_hash,
                            7,
                            "available",
                            "staging/stale.partial",
                            "{}",
                            "2026-07-29T00:00:00Z",
                        ),
                    )
            with connection:
                connection.execute(
                    """
                    INSERT INTO artifacts (
                        id, media_type, blob_hash, size, state, temp_ref,
                        retention_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        "text/plain",
                        blob_hash,
                        7,
                        "staged",
                        "staging/probe.partial",
                        "{}",
                        "2026-07-29T00:00:00Z",
                    ),
                )
            for event_type in (
                "artifact.staged",
                "artifact.committed",
                "artifact.reconciled",
            ):
                with self.subTest(event_type=event_type):
                    with self.assertRaises(sqlite3.IntegrityError):
                        with connection:
                            connection.execute(
                                """
                                INSERT INTO events (
                                    aggregate_type, aggregate_id,
                                    aggregate_version, actor_json, type,
                                    payload_json, occurred_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    "artifact",
                                    artifact_id,
                                    1,
                                    '{"kind":"system"}',
                                    event_type,
                                    "{}",
                                    "2026-07-29T00:00:00Z",
                                ),
                            )
            with connection:
                connection.execute(
                    """
                    INSERT INTO events (
                        aggregate_type, aggregate_id, aggregate_version,
                        actor_json, type, payload_json, occurred_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "artifact",
                        artifact_id,
                        1,
                        '{"kind":"system"}',
                        "artifact.staged",
                        json.dumps(
                            {
                                "artifact_id": artifact_id,
                                "state": "staged",
                                "temp_ref": "staging/probe.partial",
                                "blob_hash": blob_hash,
                                "size": 7,
                                "media_type": "text/plain",
                            }
                        ),
                        "2026-07-29T00:00:00Z",
                    ),
                )
        finally:
            connection.close()

    def test_storage_enforces_cross_field_domain_invariants(self) -> None:
        connection = initialize_database(self.path)
        try:
            # These probes target CHECK constraints, not parent existence.
            connection.execute("PRAGMA foreign_keys = OFF")
            invalid_rows = (
                (
                    """
                    INSERT INTO runs (
                        id, project_id, inquiry_id, state, snapshot_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("run-1", "p", "i", "succeeded", "{}", "now"),
                ),
                (
                    """
                    INSERT INTO approvals (
                        id, subject_type, subject_id, subject_hash,
                        capability_json, parameter_summary_json,
                        requested_effects_json, data_class, budget_json,
                        risk_tier, reversible, allowed_uses, expires_at,
                        decision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "approval-1",
                        "action",
                        "action-1",
                        "sha256:" + "a" * 64,
                        "{}",
                        "{}",
                        "{}",
                        "public",
                        "{}",
                        "T3",
                        1,
                        1,
                        "later",
                        "approved",
                    ),
                ),
                (
                    """
                    INSERT INTO locators (
                        id, resource_id, locator_type, coordinates_json,
                        status, revision
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "locator-1",
                        "resource-1",
                        "pdf",
                        '{"kind":"web"}',
                        "valid",
                        1,
                    ),
                ),
                (
                    """
                    INSERT INTO findings (
                        id, inquiry_id, statement, status, confidence_basis,
                        evidence_ids_json, revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "finding-1",
                        "inquiry-1",
                        "statement",
                        "draft",
                        "basis",
                        "[]",
                        1,
                    ),
                ),
            )
            for statement, parameters in invalid_rows:
                with self.subTest(statement=statement.split()[2]):
                    with self.assertRaises(sqlite3.IntegrityError):
                        with connection:
                            connection.execute(statement, parameters)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
