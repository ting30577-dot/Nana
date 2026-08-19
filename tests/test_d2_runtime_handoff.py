"""D2-07 D2RuntimeHandoff replay fixture gate."""

from __future__ import annotations

import json
import unittest
from collections import defaultdict
from pathlib import Path

from nana_sidecar.contracts.authorization import ActionHashMaterial, compute_action_hash
from nana_sidecar.contracts.common import effect_scope_is_subset, EffectScope


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_FIXTURE = (
    ROOT / "fixtures" / "v0.3.0-dev" / "d2_runtime_handoff_replay.json"
)


class D2RuntimeHandoffTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.fixture = json.loads(HANDOFF_FIXTURE.read_text(encoding="utf-8"))

    def test_handoff_metadata_and_preflight_are_frozen(self) -> None:
        self.assertEqual(self.fixture["schema_version"], 2)
        self.assertEqual(
            self.fixture["handoff_version"],
            "v0.3.0-dev-d2-runtime-handoff-3",
        )
        self.assertEqual(
            self.fixture["seed"],
            "nana-d2-runtime-handoff-2026-08-01",
        )
        self.assertEqual(
            self.fixture["semantics"]["openapi_runtime_merge"],
            "D3 decision; D2 exposes no runtime mutation route",
        )
        self.assertIn("must not render as success", self.fixture["semantics"]["effect_unknown"])
        self.assertIn("settle every running process", self.fixture["semantics"]["running_cancel"])
        self.assertIn("not resumable pause", self.fixture["semantics"]["running_cancel"])
        self.assertIn("release", self.fixture["semantics"]["orphaned_budget"])
        self.assertIn("advisory", self.fixture["semantics"]["observed_effects"])
        preflight = self.fixture["workspace_lock_preflight"]
        self.assertTrue(preflight["required_before_real_mutation_serving"])
        self.assertEqual(
            set(preflight["required_tests"]),
            {
                "lock_acquired_before_writable_sqlite_open",
                "ready_after_reconciliation",
                "second_instance_fails_closed",
                "lock_release_after_sqlite_close",
            },
        )

    def test_event_run_and_aggregate_sequences_are_replayable(self) -> None:
        events = self.fixture["events"]
        self.assertEqual([event["id"] for event in events], list(range(1, len(events) + 1)))
        run_events = [event for event in events if event["run_id"] == self.fixture["run"]["id"]]
        self.assertEqual(
            [event["run_seq"] for event in run_events],
            list(range(1, len(run_events) + 1)),
        )

        by_aggregate: dict[tuple[str, str], list[int]] = defaultdict(list)
        for event in events:
            by_aggregate[(event["aggregate_type"], event["aggregate_id"])].append(
                event["aggregate_version"]
            )
        for versions in by_aggregate.values():
            self.assertEqual(versions, list(range(1, len(versions) + 1)))

    def test_outbox_is_retain_only_replay_index(self) -> None:
        event_ids = [event["id"] for event in self.fixture["events"]]
        outbox_ids = self.fixture["outbox_event_ids"]
        self.assertEqual(outbox_ids, event_ids)
        self.assertEqual(len(outbox_ids), len(set(outbox_ids)))

    def test_receipt_preserves_authorization_effects_and_usage(self) -> None:
        receipt = self.fixture["receipts"][0]
        action = self.fixture["actions"][0]
        self.assertEqual(receipt["action_id"], action["id"])
        self.assertEqual(receipt["authorization_ref"], action["authorization_ref"])
        self.assertEqual(receipt["authorization_source"], "policy_grant")
        authorized = EffectScope(**receipt["authorized_effects"])
        actual = EffectScope(**receipt["actual_effects"])
        self.assertTrue(effect_scope_is_subset(actual, authorized))
        self.assertFalse(receipt["effect_violation"])
        self.assertEqual(receipt["result"], "succeeded")
        self.assertGreaterEqual(receipt["resource_usage"]["wall_clock_ms"], 0)
        self.assertIn("builtin:python.unittest.locked", actual.processes)

    def test_durable_authorization_material_is_bound_to_authorization_event(self) -> None:
        durable = self.fixture["action_authorizations"][0]
        action = self.fixture["actions"][0]
        material = ActionHashMaterial.model_validate(durable["material"])
        self.assertEqual(durable["action_id"], action["id"])
        self.assertEqual(durable["authorization_ref"], action["authorization_ref"])
        self.assertEqual(durable["action_hash"], compute_action_hash(material))
        event = next(
            event
            for event in self.fixture["events"]
            if event["id"] == durable["authorization_event_id"]
        )
        self.assertEqual(event["type"], "action.authorized")
        self.assertEqual(event["action_id"], action["id"])

    def test_artifact_projection_preserves_committed_and_reconciled_available(self) -> None:
        projection = self.fixture["artifact_projection"]
        self.assertEqual(projection["artifact.committed:available"], "available")
        self.assertEqual(projection["artifact.reconciled:available"], "available")
        artifact_events = {
            (event["type"], event["payload"]["state"])
            for event in self.fixture["events"]
            if event["aggregate_type"] == "artifact"
        }
        self.assertIn(("artifact.committed", "available"), artifact_events)
        self.assertIn(("artifact.reconciled", "available"), artifact_events)

    def test_command_idempotency_and_structured_errors_are_explicit(self) -> None:
        idempotency = self.fixture["command_idempotency"]
        self.assertEqual(
            idempotency["same_command_id_same_hash"],
            "return_stored_result_without_side_effect",
        )
        self.assertEqual(idempotency["same_command_id_different_hash"], "conflict")
        self.assertEqual(
            idempotency["rejected_replay"],
            "return_bound_error_without_reexecution",
        )
        self.assertTrue(
            {
                "E_CAPABILITY_UNREGISTERED",
                "E_POLICY_GRANT_DENIED",
                "E_APPROVAL_DENIED",
                "E_ACTION_NOT_AUTHORIZED",
                "E_ACTION_CANCEL_RACE",
                "E_RUN_BUDGET_INVALID",
                "E_RUN_CONCURRENCY_LIMIT",
                "E_ACTION_AUTHORIZATION_MISSING",
                "E_ACTION_AUTHORIZATION_INVALID",
                "E_ACTION_AUTHORIZATION_MISMATCH",
                "E_ARGS_ARTIFACT_SIZE",
                "E_ARGS_ARTIFACT_BUDGET",
            }
            <= set(self.fixture["structured_errors"])
        )


if __name__ == "__main__":
    unittest.main()
