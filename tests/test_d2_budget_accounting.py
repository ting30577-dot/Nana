"""D2-05 runtime budget accounting tests."""

from __future__ import annotations

import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path

from nana_sidecar.contracts.common import ActorKind, ActorRef, ResourceUsage
from nana_sidecar.storage import (
    BudgetAccountingService,
    RunSchedulerService,
    SchedulerStateError,
    connect_database,
    initialize_database,
)


NOW = "2026-07-31T00:00:00Z"
HASH = "sha256:" + "c" * 64


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _budget(
    *,
    max_actions: int = 4,
    max_concurrency: int = 1,
    max_output_bytes: int = 1024,
) -> dict[str, object]:
    return {
        "wall_clock_seconds": 60,
        "cpu_seconds": None,
        "memory_bytes": None,
        "gpu_seconds": None,
        "max_actions": max_actions,
        "max_concurrency": max_concurrency,
        "max_model_calls": 0,
        "max_model_tokens": 0,
        "max_cost_micros": 0,
        "max_retries": 0,
        "max_output_bytes": max_output_bytes,
        "max_artifact_bytes": 1024,
        "max_download_bytes": 0,
        "network_targets": [],
        "read_roots": [],
        "write_roots": [],
    }


def _snapshot(budget: dict[str, object]) -> dict[str, object]:
    return {
        "plan_id": "plan-1",
        "plan_revision": 1,
        "capabilities": [],
        "models": [],
        "backend": {"id": "builtin_local", "version": "1", "digest": None},
        "policy": {},
        "budget": budget,
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


class D2BudgetAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace" / "nana-vnext.db"
        self.connection = initialize_database(self.path)
        self.actor = ActorRef(kind=ActorKind.SYSTEM, id="d2-budget-test")

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _seed(
        self,
        *,
        budget: dict[str, object] | None = None,
        actions: tuple[str, ...] = ("action-1", "action-2"),
    ) -> None:
        budget = budget or _budget()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO workspaces (
                    id, schema_version, data_root, policy_json, status,
                    revision, created_at
                ) VALUES (?, 5, ?, '{}', 'active', 1, ?)
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
                ("project-1", "workspace-1", "D2 budget", NOW),
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
                    _json(budget),
                    NOW,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO runs (
                    id, project_id, inquiry_id, state, snapshot_json,
                    created_at
                ) VALUES (?, ?, ?, 'running', ?, ?)
                """,
                ("run-1", "project-1", "inquiry-1", _json(_snapshot(budget)), NOW),
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
            for action_id in actions:
                self.connection.execute(
                    """
                    INSERT INTO actions (
                        id, run_id, plan_step_id, capability_id,
                        capability_version, executable_digest,
                        args_artifact_id, args_hash, action_hash, risk_tier,
                        requested_effects_json, policy_decision,
                        authorization_ref, state
                    ) VALUES (?, 'run-1', 'step-1', 'test.capability', '1', ?,
                        'args-1', ?, ?, 'T1', ?, 'auto', 'policy:test',
                        'authorized')
                    """,
                    (
                        action_id,
                        HASH,
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
                    ),
                )

    def _claim(self, action_id: str):
        return RunSchedulerService(self.connection, now=lambda: NOW).claim_action(
            run_id="run-1",
            action_id=action_id,
            actor=self.actor,
        )

    def _record_usage(self, action_id: str, usage: ResourceUsage) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute(
                """
                UPDATE actions
                SET state = 'succeeded', finished_at = ?
                WHERE id = ?
                """,
                (NOW, action_id),
            )
            BudgetAccountingService(
                self.connection,
                now=lambda: NOW,
            ).record_action_usage(
                run_id="run-1",
                action_id=action_id,
                usage=usage,
                actor=self.actor,
            )
        except Exception:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def _ledger(self) -> dict[str, object]:
        row = self.connection.execute(
            "SELECT * FROM run_budget_ledger WHERE run_id = 'run-1'"
        ).fetchone()
        return {
            "started_actions": int(row["started_actions"]),
            "running_actions": int(row["running_actions"]),
            "exhausted": int(row["exhausted"]),
            "reason": row["exhausted_reason"],
            "usage": json.loads(str(row["usage_json"])),
        }

    def _events(self) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        for row in self.connection.execute(
            "SELECT type, payload_json FROM events ORDER BY id"
        ):
            payload = json.loads(str(row["payload_json"]))
            events.append((str(row["type"]), str(payload.get("reason"))))
        return events

    def test_under_limit_usage_allows_next_action(self) -> None:
        self._seed(budget=_budget(max_actions=2, max_output_bytes=10))

        first = self._claim("action-1")
        self.assertEqual(first.kind, "claimed")
        self._record_usage(
            "action-1",
            ResourceUsage(wall_clock_ms=100, output_bytes=5),
        )
        second = self._claim("action-2")

        self.assertEqual(second.kind, "claimed")
        self.assertEqual(
            self._ledger(),
            {
                "started_actions": 2,
                "running_actions": 1,
                "exhausted": 0,
                "reason": None,
                "usage": {
                    "artifact_bytes": 0,
                    "cost_micros": 0,
                    "cpu_ms": None,
                    "model_tokens": 0,
                    "output_bytes": 5,
                    "peak_memory_bytes": None,
                    "wall_clock_ms": 100,
                },
            },
        )

    def test_exact_output_limit_blocks_new_action(self) -> None:
        self._seed(budget=_budget(max_actions=2, max_output_bytes=10))

        self._claim("action-1")
        self._record_usage(
            "action-1",
            ResourceUsage(wall_clock_ms=100, output_bytes=10),
        )
        result = self._claim("action-2")

        self.assertEqual(result.kind, "budget_exceeded")
        self.assertEqual(str(self._ledger()["reason"]), "output_bytes_exhausted")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = 'action-2'"
            ).fetchone()["state"],
            "authorized",
        )
        self.assertIn(
            ("run.budget_exceeded", "output_bytes_exhausted"),
            self._events(),
        )

    def test_concurrent_claim_race_does_not_overissue_max_actions(self) -> None:
        self._seed(budget=_budget(max_actions=1), actions=("action-1", "action-2"))
        self.connection.close()
        results: queue.Queue[str] = queue.Queue()

        def claim(action_id: str) -> None:
            connection = connect_database(self.path)
            try:
                service = RunSchedulerService(connection, now=lambda: NOW)
                try:
                    results.put(
                        service.claim_action(
                            run_id="run-1",
                            action_id=action_id,
                            actor=self.actor,
                        ).kind
                    )
                except SchedulerStateError as exc:
                    results.put(exc.code)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=claim, args=("action-1",)),
            threading.Thread(target=claim, args=("action-2",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.connection = connect_database(self.path)
        self.assertEqual(
            sorted(results.get_nowait() for _ in threads),
            ["budget_exceeded", "claimed"],
        )
        self.assertEqual(int(self._ledger()["started_actions"]), 1)
        running_count = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM actions WHERE state = 'running'"
            ).fetchone()[0]
        )
        self.assertEqual(running_count, 1)

    def test_effect_unknown_usage_is_not_dropped(self) -> None:
        self._seed(budget=_budget(max_actions=2, max_output_bytes=20))
        self._claim("action-1")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute(
                """
                UPDATE actions
                SET state = 'effect_unknown', finished_at = ?
                WHERE id = 'action-1'
                """,
                (NOW,),
            )
            BudgetAccountingService(
                self.connection,
                now=lambda: NOW,
            ).record_action_usage(
                run_id="run-1",
                action_id="action-1",
                usage=ResourceUsage(wall_clock_ms=250, output_bytes=7),
                actor=self.actor,
            )
        except Exception:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        else:
            self.connection.commit()

        ledger = self._ledger()
        self.assertEqual(ledger["running_actions"], 0)
        self.assertEqual(ledger["usage"]["wall_clock_ms"], 250)
        self.assertEqual(ledger["usage"]["output_bytes"], 7)


if __name__ == "__main__":
    unittest.main()
