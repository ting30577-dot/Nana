"""D0 SQLite migration, schema, and ceiling tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nana_sidecar.contracts.builtin_capabilities import (
    python_unittest_locked_registry_entry,
)
from nana_sidecar.contracts.capabilities import CapabilityRegistryEntry
from nana_sidecar.contracts.domain import EventType
from nana_sidecar.storage import (
    IncompatibleDatabaseError,
    SchemaTooNewError,
    connect_database,
    connect_database_readonly,
    initialize_database,
    plan_database_migrations,
)
from nana_sidecar.storage.database import _apply_migration
from nana_sidecar.storage.migrations import MIGRATIONS, Migration


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
    "run_budget_ledger",
    "action_authorizations",
    "external_write_fences",
    "capability_registry_entries",
    "approval_consumptions",
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

    def test_dry_run_plans_current_schema_without_creating_files(self) -> None:
        plan = plan_database_migrations(self.path)

        self.assertEqual(plan.current_version, 0)
        self.assertEqual(plan.target_version, 7)
        self.assertEqual(
            [step.name for step in plan.steps],
            [
                "0001_contract_kernel",
                "0002_d2_00_hardening",
                "0003_d2_01_action_cancelled_event",
                "0004_d2_03a_full_capability_registry",
                "0005_d2_05_run_budget_ledger",
                "0006_d2_final_authorization_material",
                "0007_d3_07_approval_and_external_write_fence",
            ],
        )
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
            registry_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(capability_registry_entries)"
                )
            }
            authorization_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(action_authorizations)"
                )
            }
        finally:
            connection.close()

        self.assertEqual(tables, EXPECTED_TABLES)
        self.assertEqual(
            registry_columns,
            {
                "capability_id",
                "capability_version",
                "executable_digest",
                "entry_json",
                "contract_digest",
                "created_at",
            },
        )
        self.assertEqual(
            authorization_columns,
            {
                "action_id",
                "action_hash",
                "material_json",
                "registry_contract_digest",
                "authorization_source",
                "authorization_ref",
                "authorization_event_id",
                "authorized_at",
            },
        )
        self.assertEqual(journal_mode, "wal")
        self.assertEqual(version, 7)
        self.assertEqual(len(history), 7)
        self.assertEqual(str(history[0]["name"]), "0001_contract_kernel")
        self.assertEqual(str(history[1]["name"]), "0002_d2_00_hardening")
        self.assertEqual(
            str(history[2]["name"]),
            "0003_d2_01_action_cancelled_event",
        )
        self.assertEqual(
            str(history[3]["name"]),
            "0004_d2_03a_full_capability_registry",
        )
        self.assertEqual(
            str(history[4]["name"]),
            "0005_d2_05_run_budget_ledger",
        )
        self.assertEqual(
            str(history[5]["name"]),
            "0006_d2_final_authorization_material",
        )
        self.assertEqual(
            str(history[6]["name"]),
            "0007_d3_07_approval_and_external_write_fence",
        )
        self.assertRegex(str(history[0]["contract_hash"]), r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(
            {"problems", "research_threads", "research_sources"} & tables
        )

    def test_existing_database_probe_retries_transient_crash_release_io(self) -> None:
        initialize_database(self.path).close()
        from nana_sidecar.storage import database as database_module

        original = database_module._current_version
        attempts = 0

        def transient_then_current(connection: sqlite3.Connection) -> int:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise sqlite3.OperationalError("disk I/O error")
            return original(connection)

        with (
            patch.object(
                database_module,
                "_current_version",
                side_effect=transient_then_current,
            ),
            patch.object(database_module.time, "sleep") as sleep,
        ):
            connection = initialize_database(self.path)
        connection.close()

        self.assertGreaterEqual(attempts, 4)
        sleep.assert_called_once_with(database_module._TRANSIENT_DISK_IO_DELAYS[0])

    def test_capability_registry_entry_json_round_trips_from_storage(self) -> None:
        entry = python_unittest_locked_registry_entry()
        connection = initialize_database(self.path)
        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO capability_registry_entries (
                        capability_id, capability_version, executable_digest,
                        entry_json, contract_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.capability.id,
                        entry.capability.version,
                        entry.capability.digest,
                        entry.model_dump_json(),
                        entry.contract_digest,
                        "2026-07-30T00:00:00Z",
                    ),
                )
            row = connection.execute(
                """
                SELECT executable_digest, contract_digest, entry_json
                FROM capability_registry_entries
                WHERE capability_id = ? AND capability_version = ?
                """,
                (entry.capability.id, entry.capability.version),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["executable_digest"], entry.capability.digest)
            self.assertEqual(row["contract_digest"], entry.contract_digest)

            restored = CapabilityRegistryEntry.model_validate_json(
                row["entry_json"]
            )
            self.assertEqual(restored, entry)
            self.assertEqual(
                restored.model_dump(mode="json"),
                entry.model_dump(mode="json"),
            )
        finally:
            connection.close()

    def test_v4_registry_digest_remains_stable_through_v6_migrations(self) -> None:
        entry = python_unittest_locked_registry_entry()
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            for migration in MIGRATIONS[:4]:
                _apply_migration(connection, migration)
            with connection:
                connection.execute(
                    """
                    INSERT INTO capability_registry_entries (
                        capability_id, capability_version, executable_digest,
                        entry_json, contract_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.capability.id,
                        entry.capability.version,
                        entry.capability.digest,
                        entry.model_dump_json(),
                        entry.contract_digest,
                        "2026-07-30T00:00:00Z",
                    ),
                )
            for migration in MIGRATIONS[4:6]:
                _apply_migration(connection, migration)
            row = connection.execute(
                """
                SELECT entry_json, contract_digest
                FROM capability_registry_entries
                WHERE capability_id = ? AND capability_version = ?
                """,
                (entry.capability.id, entry.capability.version),
            ).fetchone()
            restored = CapabilityRegistryEntry.model_validate_json(row["entry_json"])
            self.assertEqual(restored, entry)
            self.assertEqual(row["contract_digest"], entry.contract_digest)
            self.assertEqual(
                row["contract_digest"],
                "sha256:18ccf020b55ea54abd26d2132db54313e2005788bd9c91306f0f2810ee735b38",
            )
        finally:
            connection.close()

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
        self.assertEqual(count, 7)
        self.assertEqual(plan_database_migrations(self.path).steps, ())

    def test_empty_uninitialized_database_is_not_a_connectable_workspace(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.touch()
        with self.assertRaisesRegex(IncompatibleDatabaseError, "not initialized"):
            connect_database(self.path)

    def test_higher_schema_is_refused_before_writes(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA user_version = 8")
        connection.close()
        with self.assertRaisesRegex(SchemaTooNewError, "exceeds read ceiling"):
            initialize_database(self.path)
        connection = sqlite3.connect(self.path)
        try:
            journal_mode = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).lower()
        finally:
            connection.close()
        self.assertEqual(journal_mode, "delete")

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

    def test_d2_00_authorization_guards_fail_closed_in_storage(self) -> None:
        connection = initialize_database(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            invalid_rows = (
                (
                    """
                    INSERT INTO actions (
                        id, capability_id, capability_version, args_artifact_id,
                        args_hash, action_hash, risk_tier, requested_effects_json,
                        policy_decision, state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "action-missing-digest",
                        "export.draft_external",
                        "1",
                        "artifact-1",
                        "sha256:" + "a" * 64,
                        "sha256:" + "b" * 64,
                        "T3",
                        "{}",
                        "approval_required",
                        "proposed",
                    ),
                ),
                (
                    """
                    INSERT INTO policy_grants (
                        id, project_id, capability_id, capability_version,
                        constraints_json, state, uses, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "grant-missing-digest",
                        "project-1",
                        "export.draft_external",
                        "1",
                        "{}",
                        "active",
                        0,
                        "2026-07-30T00:00:00Z",
                    ),
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
                        "approval-two-uses",
                        "action",
                        "action-1",
                        "sha256:" + "c" * 64,
                        json.dumps(
                            {
                                "id": "export.publish",
                                "version": "1",
                                "digest": "sha256:" + "d" * 64,
                            }
                        ),
                        "{}",
                        "{}",
                        "public",
                        "{}",
                        "T4",
                        0,
                        2,
                        "2026-07-30T00:05:00Z",
                        "requested",
                    ),
                ),
                (
                    """
                    INSERT INTO action_receipts (
                        id, action_id, action_hash, authorization_source,
                        authorization_ref, actual_effects_json, result,
                        before_artifact_ids_json, after_artifact_ids_json,
                        resource_usage_json, created_at,
                        authorized_effects_json, effect_violation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "receipt-bad-effect",
                        "action-1",
                        "sha256:" + "e" * 64,
                        "auto_policy",
                        "policy:auto",
                        '{"writes":["external:leak"]}',
                        "succeeded",
                        "[]",
                        "[]",
                        "{}",
                        "2026-07-30T00:00:00Z",
                        '{"writes":["scratch:run"]}',
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

    def test_d2_00_event_and_outbox_retention_are_enforced(self) -> None:
        connection = initialize_database(self.path)
        try:
            with connection:
                event = connection.execute(
                    """
                    INSERT INTO events (
                        aggregate_type, aggregate_id, aggregate_version,
                        actor_json, type, payload_json, occurred_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "plan",
                        "plan-1",
                        1,
                        '{"kind":"system"}',
                        "plan.revised",
                        '{"revision":1}',
                        "2026-07-30T00:00:00Z",
                    ),
                )
                event_id = int(event.lastrowid)
                connection.execute(
                    "INSERT INTO outbox_events(event_id) VALUES (?)",
                    (event_id,),
                )
            blocked = (
                ("UPDATE events SET type = type WHERE id = ?", (event_id,)),
                ("DELETE FROM events WHERE id = ?", (event_id,)),
                ("UPDATE outbox_events SET event_id = event_id + 1 WHERE event_id = ?", (event_id,)),
                ("DELETE FROM outbox_events WHERE event_id = ?", (event_id,)),
            )
            for statement, parameters in blocked:
                with self.subTest(statement=statement):
                    with self.assertRaises(sqlite3.IntegrityError):
                        with connection:
                            connection.execute(statement, parameters)
            with connection:
                connection.execute(
                    """
                    UPDATE outbox_events
                    SET dispatched_at = ?, attempts = attempts + 1
                    WHERE event_id = ?
                    """,
                    ("2026-07-30T00:01:00Z", event_id),
                )
            row = connection.execute(
                "SELECT dispatched_at, attempts FROM outbox_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            self.assertEqual(
                (row["dispatched_at"], int(row["attempts"])),
                ("2026-07-30T00:01:00Z", 1),
            )
        finally:
            connection.close()

    def test_readonly_database_connection_cannot_write(self) -> None:
        initialize_database(self.path).close()
        connection = connect_database_readonly(self.path)
        try:
            self.assertEqual(
                int(connection.execute("PRAGMA query_only").fetchone()[0]),
                1,
            )
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute(
                    "INSERT INTO command_log (command_id, type, request_hash, actor_json, state, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "command-1",
                        "probe",
                        "sha256:" + "a" * 64,
                        "{}",
                        "accepted",
                        "2026-07-30T00:00:00Z",
                    ),
                )
        finally:
            connection.close()

    def test_v1_upgrade_refuses_unpinned_authorization_rows(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        _apply_migration(connection, MIGRATIONS[0])
        with connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """
                INSERT INTO actions (
                    id, capability_id, capability_version, args_artifact_id,
                    args_hash, action_hash, risk_tier, requested_effects_json,
                    policy_decision, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "v1-action-missing-digest",
                    "export.draft_external",
                    "1",
                    "artifact-1",
                    "sha256:" + "a" * 64,
                    "sha256:" + "b" * 64,
                    "T3",
                    "{}",
                    "approval_required",
                    "proposed",
                ),
            )
        connection.close()

        with self.assertRaises(sqlite3.IntegrityError):
            initialize_database(self.path)
        connection = sqlite3.connect(self.path)
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            missing = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'capability_registry_entries'
                """
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(version, 1)
        self.assertIsNone(missing)

    def test_v3_upgrade_refuses_incomplete_registry_rows(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        try:
            for migration in MIGRATIONS[:3]:
                _apply_migration(connection, migration)
            with connection:
                connection.execute(
                    """
                    INSERT INTO capability_registry_entries (
                        capability_id, capability_version, executable_digest,
                        args_schema_json, risk_tier, reversible,
                        authorization_mode, grantable, provider_mode,
                        allowed_providers_json, contract_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "python.unittest.locked",
                        "1",
                        "sha256:" + "a" * 64,
                        '{"type":"object","additionalProperties":false}',
                        "T1",
                        1,
                        "policy_grant",
                        1,
                        "forbidden",
                        "[]",
                        "sha256:" + "b" * 64,
                        "2026-07-30T00:00:00Z",
                    ),
                )
        finally:
            connection.close()

        with self.assertRaises(sqlite3.IntegrityError):
            initialize_database(self.path)

        connection = sqlite3.connect(self.path)
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(capability_registry_entries)"
                )
            }
        finally:
            connection.close()
        self.assertEqual(version, 3)
        self.assertIn("args_schema_json", columns)
        self.assertNotIn("entry_json", columns)

    def test_v5_upgrade_refuses_actions_with_missing_authorization_material(self) -> None:
        self.path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.path)
        try:
            for migration in MIGRATIONS[:5]:
                _apply_migration(connection, migration)
            with connection:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    """
                    INSERT INTO actions (
                        id, capability_id, capability_version,
                        executable_digest, args_artifact_id, args_hash,
                        action_hash, risk_tier, requested_effects_json,
                        policy_decision, authorization_ref, state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "v5-authorized-action",
                        "python.unittest.locked",
                        "1",
                        "sha256:" + "a" * 64,
                        "missing-artifact",
                        "sha256:" + "b" * 64,
                        "sha256:" + "c" * 64,
                        "T2",
                        "{}",
                        "grant",
                        "policy_grant:missing",
                        "authorized",
                    ),
                )
        finally:
            connection.close()

        with self.assertRaises(sqlite3.IntegrityError):
            initialize_database(self.path)

        connection = sqlite3.connect(self.path)
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            authorization_table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'action_authorizations'
                """
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(version, 5)
        self.assertIsNone(authorization_table)


if __name__ == "__main__":
    unittest.main()
