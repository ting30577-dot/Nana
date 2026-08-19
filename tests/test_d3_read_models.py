"""D3-03 canonical bootstrap read-model tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nana_sidecar.read_models import BootstrapReadModel, PageTooLargeError
from nana_sidecar.storage import initialize_database


NOW = "2026-08-01T00:00:00Z"


class BootstrapReadModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "nana.db"
        self.connection = initialize_database(self.database_path)
        self.connection.execute(
            "INSERT INTO workspaces(id, schema_version, data_root, policy_json, status, revision, created_at) "
            "VALUES (?, 7, ?, ?, 'active', 1, ?)",
            ("workspace-1", "secret-local-path", json.dumps({"secret": "never-project"}), NOW),
        )
        self._event(1, "workspace.created")
        self.connection.commit()

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _event(self, version: int, event_type: str) -> int:
        event = self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, type, payload_json, occurred_at) "
            "VALUES ('workspace', 'workspace-1', ?, ?, ?, ?, ?)",
            (version, json.dumps({"kind": "user", "id": "owner"}), event_type, json.dumps({"state": "active"}), NOW),
        )
        event_id = int(event.lastrowid)
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event_id,))
        return event_id

    def test_snapshot_is_whitelisted_and_has_outbox_high_water_and_watermark(self) -> None:
        snapshot = BootstrapReadModel(self.database_path).snapshot()
        self.assertEqual(snapshot["high_water_event_id"], 1)
        self.assertEqual(snapshot["workspace"], {"id": "workspace-1", "schema_version": 7, "status": "active", "revision": 1})
        self.assertNotIn("secret-local-path", json.dumps(snapshot))
        self.assertNotIn("never-project", json.dumps(snapshot))
        self.assertEqual(snapshot["aggregate_versions"], {"workspace:workspace-1": 1})
        self.assertEqual(snapshot["run_sequences"], {})

    def test_snapshot_projects_are_canonical_and_field_whitelisted(self) -> None:
        self.connection.execute(
            "INSERT INTO projects(id, workspace_id, title, status, data_class, revision, created_at) "
            "VALUES (?, ?, ?, 'active', 'personal', 1, ?)",
            ("project-1", "workspace-1", "Field study", NOW),
        )
        self.connection.commit()

        snapshot = BootstrapReadModel(self.database_path).snapshot()

        self.assertEqual(
            snapshot["projects"],
            [{
                "id": "project-1",
                "workspace_id": "workspace-1",
                "title": "Field study",
                "status": "active",
                "data_class": "personal",
                "revision": 1,
                "created_at": NOW,
            }],
        )
        self.assertNotIn("secret-local-path", json.dumps(snapshot))
        self.assertNotIn("never-project", json.dumps(snapshot))

    def test_snapshot_action_projection_excludes_authorization_material(self) -> None:
        self.connection.execute(
            "INSERT INTO artifacts(id, media_type, blob_hash, size, state, retention_json, created_at) "
            "VALUES (?, 'application/json', ?, 2, 'available', ?, ?)",
            ("artifact-args", "sha256:" + "a" * 64, json.dumps({}), NOW),
        )
        self.connection.execute(
            "INSERT INTO actions(id, run_id, plan_step_id, capability_id, capability_version, executable_digest, "
            "args_artifact_id, args_hash, action_hash, risk_tier, requested_effects_json, "
            "policy_decision, authorization_ref, state) VALUES (?, NULL, NULL, ?, '1', ?, ?, ?, ?, 'T2', ?, ?, ?, 'waiting_approval')",
            (
                "action-private",
                "python.unittest.locked",
                "sha256:" + "d" * 64,
                "artifact-args",
                "sha256:" + "b" * 64,
                "sha256:" + "c" * 64,
                json.dumps({"reads": [], "writes": [], "network": [], "processes": []}),
                "approval_required",
                "policy_grant:must-not-project",
            ),
        )
        self.connection.commit()
        snapshot = BootstrapReadModel(self.database_path).snapshot()
        action = next(row for row in snapshot["actions"] if row["id"] == "action-private")
        self.assertNotIn("policy_decision", action)
        self.assertNotIn("authorization_ref", action)
        self.assertNotIn("capability_version", action)
        self.assertNotIn("risk_tier", action)
        self.assertNotIn("policy_grant:must-not-project", json.dumps(snapshot))
        self.assertEqual(
            snapshot["needs_you"],
            [{
                "action_id": "action-private",
                "run_id": None,
                "state": "waiting_approval",
                "approval_id": None,
                "subject_hash": None,
                "expires_at": None,
            }],
        )

    def test_high_water_excludes_non_outbox_events(self) -> None:
        self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, type, payload_json, occurred_at) "
            "VALUES ('workspace', 'workspace-1', 2, ?, 'project.created', ?, ?)",
            (json.dumps({"kind": "user", "id": "owner"}), json.dumps({"state": "active"}), NOW),
        )
        self.connection.commit()
        snapshot = BootstrapReadModel(self.database_path).snapshot()
        self.assertEqual(snapshot["high_water_event_id"], 1)
        self.assertEqual(snapshot["aggregate_versions"], {"workspace:workspace-1": 1})

    def test_unknown_committed_event_degrades_even_when_activity_window_drops_it(self) -> None:
        event = self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, type, payload_json, occurred_at) "
            "VALUES ('budget', 'budget-old', 1, ?, 'run.started', ?, ?)",
            (json.dumps({"kind": "system"}), json.dumps({"state": "unknown"}), NOW),
        )
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event.lastrowid,))
        for version in range(2, 203):
            self._event(version, "workspace.created")
        self.connection.commit()
        snapshot = BootstrapReadModel(self.database_path).snapshot()
        self.assertEqual(snapshot["projection_status"], "degraded")
        self.assertNotIn("run.started", [row["type"] for row in snapshot["activity"]])

    def test_unknown_committed_event_pair_degrades_even_when_activity_window_drops_it(self) -> None:
        event = self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, type, payload_json, occurred_at) "
            "VALUES ('workspace', 'workspace-1', 2, ?, 'project.created', ?, ?)",
            (json.dumps({"kind": "system"}), json.dumps({"state": "must-not-infer"}), NOW),
        )
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event.lastrowid,))
        for version in range(3, 204):
            self._event(version, "workspace.created")
        self.connection.commit()
        snapshot = BootstrapReadModel(self.database_path).snapshot()
        self.assertEqual(snapshot["projection_status"], "degraded")
        self.assertNotIn("project.created", [row["type"] for row in snapshot["activity"]])

    def test_activity_pages_and_watermarks_exclude_non_outbox_events_below_later_high_water(self) -> None:
        # Simulate a row written to the Event table before its outbox publication.
        self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, type, payload_json, occurred_at) "
            "VALUES ('run', 'run-unpublished', 1, ?, 'run.started', ?, ?)",
            (json.dumps({"kind": "system"}), json.dumps({"state": "must-not-project"}), NOW),
        )
        self._event(3, "workspace.created")
        self.connection.commit()
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        snapshot = model.snapshot()
        self.assertEqual(snapshot["high_water_event_id"], 3)
        self.assertEqual([row["id"] for row in snapshot["activity"]], [1, 3])
        self.assertNotIn("must-not-project", json.dumps(snapshot))
        self.assertEqual(snapshot["aggregate_versions"], {"workspace:workspace-1": 3})
        self.assertEqual(snapshot["run_sequences"], {})
        token = model._encode_token(
            3,
            "activity",
            0,
            {"aggregate_versions": snapshot["aggregate_versions"], "run_sequences": snapshot["run_sequences"]},
        )
        page = model.page(section="activity", token=token, limit=10)
        self.assertEqual([row["id"] for row in page["rows"]], [1, 3])

    def test_signed_page_token_uses_unambiguous_payload_and_signature_parts(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        for offset in range(64):
            token = model._encode_token(1, "activity", offset, {"aggregate_versions": {}, "run_sequences": {}})
            self.assertEqual(model._decode_token(token)["offset"], offset)

    def test_page_token_is_bound_to_the_runtime_session_secret(self) -> None:
        issuer = BootstrapReadModel(self.database_path, token_secret="session-a-secret")
        other_session = BootstrapReadModel(self.database_path, token_secret="session-b-secret")
        token = issuer._encode_token(1, "activity", 0, {"aggregate_versions": {}, "run_sequences": {}})
        with self.assertRaisesRegex(ValueError, "E_PAGE_TOKEN"):
            other_session._decode_token(token)

    def test_activity_page_reuses_anchored_watermark_after_later_event(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        snapshot = model.snapshot()
        token = model._encode_token(
            int(snapshot["high_water_event_id"]),
            "activity",
            0,
            {"aggregate_versions": snapshot["aggregate_versions"], "run_sequences": snapshot["run_sequences"]},
        )
        self._event(2, "workspace.created")
        self.connection.commit()
        page = model.page(section="activity", token=token, limit=100)
        self.assertEqual(page["high_water_event_id"], 1)
        self.assertEqual([row["id"] for row in page["rows"]], [1])
        self.assertEqual(page["aggregate_versions"], {"workspace:workspace-1": 1})

    def test_page_token_tampering_fails_closed(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        snapshot = model.snapshot()
        token = model._encode_token(
            int(snapshot["high_water_event_id"]), "activity", 0,
            {"aggregate_versions": snapshot["aggregate_versions"], "run_sequences": snapshot["run_sequences"]},
        )
        with self.assertRaisesRegex(ValueError, "E_PAGE_TOKEN"):
            model.page(section="activity", token=token[:-1] + ("A" if token[-1] != "A" else "B"))
        for malformed in (token + "!", token.replace(".", "..", 1), None):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(ValueError, "E_PAGE_TOKEN"):
                    model._decode_token(malformed)  # type: ignore[arg-type]

    def test_section_page_is_event_anchored_across_later_write(self) -> None:
        self._event(2, "workspace.created")
        self.connection.commit()
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        snapshot = model.snapshot()
        token = model._encode_token(
            int(snapshot["high_water_event_id"]), "research", 0,
            {"aggregate_versions": snapshot["aggregate_versions"], "run_sequences": snapshot["run_sequences"]},
        )
        first = model.page(section="research", token=token, limit=1)
        self._event(3, "workspace.created")
        self.connection.commit()
        second_token = first["next_page_token"] or token
        second = model.page(section="research", token=second_token, limit=1)
        self.assertEqual(first["high_water_event_id"], 2)
        self.assertEqual(second["high_water_event_id"], 2)
        self.assertNotIn(3, [row["id"] for row in second["rows"]])

    def test_same_token_and_offset_are_idempotent_across_later_write(self) -> None:
        self._event(2, "workspace.created")
        self.connection.commit()
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        snapshot = model.snapshot()
        token = model._encode_token(
            int(snapshot["high_water_event_id"]), "research", 0,
            {"aggregate_versions": snapshot["aggregate_versions"], "run_sequences": snapshot["run_sequences"]},
        )
        before = model.page(section="research", token=token, limit=10)
        self._event(3, "workspace.created")
        self.connection.commit()
        after = model.page(section="research", token=token, limit=10)
        self.assertEqual(before, after)

    def test_cross_section_token_is_rejected(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        token = model._encode_token(1, "research", 0, {"aggregate_versions": {}, "run_sequences": {}})
        with self.assertRaisesRegex(ValueError, "E_PAGE_TOKEN_SECTION"):
            model.page(section="execution", token=token)

    def test_page_offset_bounds_are_rejected(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        with self.assertRaisesRegex(ValueError, "E_PAGE_TOKEN"):
            model._decode_token(model._encode_token(1, "activity", -1, {"aggregate_versions": {}, "run_sequences": {}}))

    def test_page_token_boolean_numbers_are_rejected(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        for high_water, offset in ((True, 0), (1, True)):
            token = model._encode_token(high_water, "activity", offset, {"aggregate_versions": {}, "run_sequences": {}})  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "E_PAGE_TOKEN"):
                model._decode_token(token)

    def test_section_page_over_ceiling_fails_without_silent_truncation(self) -> None:
        model = BootstrapReadModel(self.database_path, token_secret="test-secret")
        token = model._encode_token(1, "activity", 0, {"aggregate_versions": {}, "run_sequences": {}})
        with patch("nana_sidecar.read_models.MAX_BOOTSTRAP_BYTES", 1):
            with self.assertRaises(PageTooLargeError):
                model.page(section="activity", token=token, limit=1)


if __name__ == "__main__":
    unittest.main()
