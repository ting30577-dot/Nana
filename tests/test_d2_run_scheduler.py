"""D2-01 scheduler admission and cancellation tests."""

from __future__ import annotations

import json
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path

from nana_sidecar.contracts.common import ActorKind, ActorRef
from nana_sidecar.storage import (
    RunSchedulerService,
    SchedulerResult,
    SchedulerStateError,
    connect_database,
    initialize_database,
)


NOW = "2026-07-30T00:00:00Z"
HASH = "sha256:" + "a" * 64


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _budget(max_actions: int) -> dict[str, object]:
    return {
        "wall_clock_seconds": 60,
        "cpu_seconds": None,
        "memory_bytes": None,
        "gpu_seconds": None,
        "max_actions": max_actions,
        "max_concurrency": 1,
        "max_model_calls": 0,
        "max_model_tokens": 0,
        "max_cost_micros": 0,
        "max_retries": 0,
        "max_output_bytes": 1024,
        "max_artifact_bytes": 1024,
        "max_download_bytes": 0,
        "network_targets": [],
        "read_roots": [],
        "write_roots": [],
    }


def _snapshot(max_actions: int) -> dict[str, object]:
    return {
        "plan_id": "plan-1",
        "plan_revision": 1,
        "capabilities": [],
        "models": [],
        "backend": {"id": "builtin_local", "version": "1", "digest": None},
        "policy": {},
        "budget": _budget(max_actions),
        "code": {"commit_ref": None, "diff_hash": None, "dirty": False},
        "input_artifact_ids": [],
        "environment": {
            "os_name": "Windows",
            "os_version": "test",
            "python_version": "3.12",
            "dependency_lock_hash": HASH,
            "environment_keys": [],
        },
        "random_seed": 7,
    }


class D2RunSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace" / "nana-vnext.db"
        self.connection = initialize_database(self.path)
        self.actor = ActorRef(kind=ActorKind.SYSTEM, id="d2-test")
        self.service = RunSchedulerService(
            self.connection,
            now=lambda: NOW,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _seed(
        self,
        *,
        run_state: str = "running",
        max_actions: int = 5,
        actions: tuple[tuple[str, str, str | None], ...] = (
            ("action-1", "authorized", None),
        ),
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO workspaces (
                    id, schema_version, data_root, policy_json, status,
                    revision, created_at
                ) VALUES (?, 3, ?, '{}', 'active', 1, ?)
                """,
                ("workspace-1", "workspace-root", NOW),
            )
            self.connection.execute(
                """
                INSERT INTO projects (
                    id, workspace_id, title, status, data_class, revision,
                    created_at
                ) VALUES (?, ?, ?, 'active', 'public', 1, ?)
                """,
                ("project-1", "workspace-1", "D2 test", NOW),
            )
            self.connection.execute(
                """
                INSERT INTO inquiries (
                    id, project_id, question, acceptance, status, revision,
                    created_at
                ) VALUES (?, ?, ?, ?, 'active', 1, ?)
                """,
                ("inquiry-1", "project-1", "Question", "Acceptance", NOW),
            )
            self.connection.execute(
                """
                INSERT INTO plans (
                    id, inquiry_id, revision, status, steps_json, policy_json,
                    budget_json, created_at
                ) VALUES (?, ?, 1, 'approved', ?, '{}', ?, ?)
                """,
                (
                    "plan-1",
                    "inquiry-1",
                    _json([{"id": "step-1", "title": "Step"}]),
                    _json(_budget(max_actions)),
                    NOW,
                ),
            )
            finished_at = NOW if run_state in {
                "succeeded",
                "failed",
                "cancelled",
                "timed_out",
                "budget_exceeded",
                "orphaned",
            } else None
            self.connection.execute(
                """
                INSERT INTO runs (
                    id, project_id, inquiry_id, state, snapshot_json,
                    result_json, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "run-1",
                    "project-1",
                    "inquiry-1",
                    run_state,
                    _json(_snapshot(max_actions)),
                    _json({"state": run_state}) if finished_at else None,
                    NOW,
                    finished_at,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO artifacts (
                    id, media_type, blob_hash, size, state, retention_json,
                    created_at
                ) VALUES (?, 'application/json', ?, 2, 'available', '{}', ?)
                """,
                ("args-1", HASH, NOW),
            )
            for action_id, state, started_at in actions:
                self.connection.execute(
                    """
                    INSERT INTO actions (
                        id, run_id, plan_step_id, capability_id,
                        capability_version, executable_digest,
                        args_artifact_id, args_hash, action_hash, risk_tier,
                        requested_effects_json, policy_decision,
                        authorization_ref, state, started_at, finished_at
                    ) VALUES (?, ?, 'step-1', 'test.capability', '1', ?, ?,
                        ?, ?, 'T1', ?, 'auto', 'policy:test', ?, ?, ?)
                    """,
                    (
                        action_id,
                        "run-1",
                        HASH,
                        "args-1",
                        HASH,
                        HASH,
                        _json(
                            {
                                "reads": [],
                                "writes": [],
                                "network": [],
                                "processes": [],
                            }
                        ),
                        state,
                        started_at,
                        NOW if state in {
                            "succeeded",
                            "failed",
                            "cancelled",
                            "timed_out",
                            "effect_unknown",
                        } else None,
                    ),
                )

    def _events(self) -> list[dict[str, object]]:
        return [
            {
                "id": int(row["id"]),
                "type": str(row["type"]),
                "run_seq": int(row["run_seq"]),
                "action_id": row["action_id"],
                "payload": json.loads(str(row["payload_json"])),
            }
            for row in self.connection.execute(
                """
                SELECT id, type, run_seq, action_id, payload_json
                FROM events
                ORDER BY id
                """
            )
        ]

    def _action_state(self, action_id: str) -> str:
        return str(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?",
                (action_id,),
            ).fetchone()["state"]
        )

    def test_claim_authorized_action_once_and_records_started_event(self) -> None:
        self._seed()

        result = self.service.claim_action(
            run_id="run-1",
            action_id="action-1",
            actor=self.actor,
        )

        self.assertEqual(result.kind, "claimed")
        self.assertEqual(self._action_state("action-1"), "running")
        self.assertEqual(
            [(event["type"], event["run_seq"]) for event in self._events()],
            [("budget.updated", 1), ("action.started", 2)],
        )
        outbox_count = int(
            self.connection.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0]
        )
        self.assertEqual(outbox_count, 2)

        with self.assertRaises(SchedulerStateError):
            time.sleep(0.25)
            self.service.claim_action(
                run_id="run-1",
                action_id="action-1",
                actor=self.actor,
            )
        self.assertEqual(len(self._events()), 2)

    def test_invalid_claims_fail_without_state_pollution(self) -> None:
        self._seed(actions=(("action-1", "proposed", None),))

        with self.assertRaisesRegex(
            SchedulerStateError,
            "Action is not authorized",
        ):
            self.service.claim_action(
                run_id="run-1",
                action_id="action-1",
                actor=self.actor,
            )

        self.assertEqual(self._action_state("action-1"), "proposed")
        self.assertEqual(self._events(), [])

    def test_max_actions_count_gate_finishes_run_without_starting_action(self) -> None:
        self._seed(
            max_actions=1,
            actions=(
                ("action-started", "succeeded", NOW),
                ("action-2", "authorized", None),
            ),
        )

        result = self.service.claim_action(
            run_id="run-1",
            action_id="action-2",
            actor=self.actor,
        )

        self.assertEqual(result.kind, "budget_exceeded")
        run = self.connection.execute(
            "SELECT state, finished_at FROM runs WHERE id = 'run-1'"
        ).fetchone()
        self.assertEqual(str(run["state"]), "budget_exceeded")
        self.assertEqual(str(run["finished_at"]), NOW)
        self.assertEqual(self._action_state("action-2"), "authorized")
        self.assertEqual(
            [(event["type"], event["payload"]["reason"]) for event in self._events()],
            [
                ("budget.threshold_reached", "max_actions_exhausted"),
                ("run.budget_exceeded", "max_actions_exhausted"),
            ],
        )

    def test_cancel_run_pauses_until_running_action_is_settled(self) -> None:
        self._seed(
            actions=(
                ("action-proposed", "proposed", None),
                ("action-waiting", "waiting_approval", None),
                ("action-authorized", "authorized", None),
                ("action-running", "running", NOW),
            )
        )

        result = self.service.cancel_run(
            run_id="run-1",
            actor=self.actor,
            reason="user requested stop",
        )

        self.assertEqual(result.kind, "cancellation_requested")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM runs WHERE id = 'run-1'"
            ).fetchone()["state"],
            "paused",
        )
        self.assertEqual(self._action_state("action-proposed"), "cancelled")
        self.assertEqual(self._action_state("action-waiting"), "cancelled")
        self.assertEqual(self._action_state("action-authorized"), "cancelled")
        self.assertEqual(self._action_state("action-running"), "running")
        event_types = [event["type"] for event in self._events()]
        self.assertEqual(event_types.count("action.cancelled"), 3)
        self.assertIn("run.paused", event_types)
        self.assertNotIn("action.effect_unknown", event_types)
        self.assertNotIn("action.completed", event_types)
        self.assertEqual(
            [event["run_seq"] for event in self._events()],
            list(range(1, 5)),
        )

        with self.assertRaises(SchedulerStateError):
            self.service.claim_action(
                run_id="run-1",
                action_id="action-authorized",
                actor=self.actor,
            )

    def test_cancel_terminal_run_is_idempotent_and_adds_no_event(self) -> None:
        self._seed(run_state="cancelled")

        result = self.service.cancel_run(
            run_id="run-1",
            actor=self.actor,
            reason="repeat",
        )

        self.assertEqual(result.kind, "already_terminal")
        self.assertEqual(result.event_ids, ())
        self.assertEqual(self._events(), [])

    def test_two_connections_racing_same_action_claim_once(self) -> None:
        self._seed()
        self.connection.close()
        results: queue.Queue[str] = queue.Queue()

        def claim() -> None:
            connection = connect_database(self.path)
            try:
                service = RunSchedulerService(connection, now=lambda: NOW)
                try:
                    outcome = service.claim_action(
                        run_id="run-1",
                        action_id="action-1",
                        actor=self.actor,
                    )
                    results.put(outcome.kind)
                except SchedulerStateError as exc:
                    results.put(exc.code)
            finally:
                connection.close()

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.connection = connect_database(self.path)
        self.assertEqual(
            sorted(results.get_nowait() for _ in threads),
            ["E_ACTION_NOT_AUTHORIZED", "claimed"],
        )
        self.assertEqual(self._action_state("action-1"), "running")
        self.assertEqual(
            [event["type"] for event in self._events()],
            ["budget.updated", "action.started"],
        )

    def test_claim_cancel_race_never_starts_a_cancelled_action(self) -> None:
        self._seed()
        self.connection.close()
        results: queue.Queue[str] = queue.Queue()

        def claim() -> None:
            connection = connect_database(self.path)
            try:
                service = RunSchedulerService(connection, now=lambda: NOW)
                try:
                    results.put(
                        service.claim_action(
                            run_id="run-1",
                            action_id="action-1",
                            actor=self.actor,
                        ).kind
                    )
                except SchedulerStateError as exc:
                    results.put(exc.code)
            finally:
                connection.close()

        def cancel() -> None:
            connection = connect_database(self.path)
            try:
                service = RunSchedulerService(connection, now=lambda: NOW)
                results.put(
                    service.cancel_run(
                        run_id="run-1",
                        actor=self.actor,
                        reason="race cancel",
                    ).kind
                )
            finally:
                connection.close()

        threads = [threading.Thread(target=claim), threading.Thread(target=cancel)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.connection = connect_database(self.path)
        run_state = str(
            self.connection.execute(
                "SELECT state FROM runs WHERE id = 'run-1'"
            ).fetchone()["state"]
        )
        action_state = self._action_state("action-1")
        self.assertIn(run_state, {"cancelled", "paused"})
        self.assertIn(action_state, {"cancelled", "running"})
        event_types = [event["type"] for event in self._events()]
        if action_state == "cancelled":
            self.assertNotIn("action.started", event_types)
            self.assertIn("action.cancelled", event_types)
        else:
            self.assertIn("action.started", event_types)
            self.assertIn("run.paused", event_types)
            self.assertNotIn("action.effect_unknown", event_types)
        self.assertNotIn("action.completed", event_types)
