"""D1-05 gate for Command idempotency, revision, and outbox atomicity."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from uuid import UUID, uuid4

from nana_sidecar.contracts.commands import (
    CommandStatus,
    RevisePlan,
)
from nana_sidecar.contracts.common import ActorRef, BudgetSnapshot
from nana_sidecar.contracts.domain import PlanStep
from nana_sidecar.contracts.errors import ErrorCode
from nana_sidecar.storage import connect_database, initialize_database
from nana_sidecar.storage.command_transactions import (
    CommandExecutionError,
    CommandTransactionService,
)


NOW = "2026-07-30T00:00:00Z"


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class InjectedCommandCrash(RuntimeError):
    pass


class CrashOnce:
    def __init__(self, target: str) -> None:
        self.target = target
        self.fired = False

    def __call__(self, checkpoint: str) -> None:
        if checkpoint == self.target and not self.fired:
            self.fired = True
            raise InjectedCommandCrash(checkpoint)


class D1CommandTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "nana.db"
        self.connection = initialize_database(self.database_path)
        self.workspace_id = UUID("00000000-0000-0000-0000-000000000101")
        self.project_id = UUID("00000000-0000-0000-0000-000000000102")
        self.inquiry_id = UUID("00000000-0000-0000-0000-000000000103")
        self.plan_id = UUID("00000000-0000-0000-0000-000000000104")
        self.actor = ActorRef(kind="user", id="owner")
        self.budget = BudgetSnapshot(
            wall_clock_seconds=60,
            max_actions=4,
            max_concurrency=1,
            max_model_calls=0,
            max_model_tokens=0,
            max_cost_micros=0,
            max_retries=0,
            max_output_bytes=4096,
            max_artifact_bytes=4096,
            max_download_bytes=0,
        )
        self._insert_baseline()

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _insert_baseline(self) -> None:
        self.connection.execute(
            """
            INSERT INTO workspaces (
                id, schema_version, data_root, policy_json, status,
                revision, created_at
            ) VALUES (?, 1, 'workspace', '{}', 'active', 1, ?)
            """,
            (str(self.workspace_id), NOW),
        )
        self.connection.execute(
            """
            INSERT INTO projects (
                id, workspace_id, title, status, data_class, revision, created_at
            ) VALUES (?, ?, 'Nana', 'active', 'public', 1, ?)
            """,
            (str(self.project_id), str(self.workspace_id), NOW),
        )
        self.connection.execute(
            """
            INSERT INTO inquiries (
                id, project_id, question, acceptance, status, revision,
                created_at
            ) VALUES (?, ?, 'Question', 'Acceptance', 'draft', 1, ?)
            """,
            (str(self.inquiry_id), str(self.project_id), NOW),
        )
        self.connection.execute(
            """
            INSERT INTO plans (
                id, inquiry_id, revision, status, steps_json, policy_json,
                budget_json, created_at
            ) VALUES (?, ?, 1, 'proposed', ?, ?, ?, ?)
            """,
            (
                str(self.plan_id),
                str(self.inquiry_id),
                _json(
                    [
                        {
                            "id": "step-1",
                            "title": "Initial",
                            "capability_id": None,
                            "expected_artifacts": [],
                            "approval_required": False,
                        }
                    ]
                ),
                _json({"mode": "manual"}),
                _json(self.budget.model_dump(mode="json")),
                NOW,
            ),
        )
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES ('plan', ?, 1, ?, 'plan.proposed', ?, ?)
            """,
            (
                str(self.plan_id),
                _json(self.actor.model_dump(mode="json")),
                _json({"plan_id": str(self.plan_id), "revision": 1}),
                NOW,
            ),
        )
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (int(cursor.lastrowid),),
        )
        self.connection.commit()

    def _command(
        self,
        *,
        command_id: UUID | None = None,
        expected_revision: int | None = 1,
        title: str = "Revised",
        actor: ActorRef | None = None,
    ) -> RevisePlan:
        return RevisePlan(
            type="RevisePlan",
            command_id=command_id or uuid4(),
            expected_revision=expected_revision,
            actor=actor or self.actor,
            plan_id=self.plan_id,
            steps=(PlanStep(id="step-1", title=title),),
            policy={"mode": "manual"},
            budget=self.budget,
        )

    def _service(self, checkpoint=None) -> CommandTransactionService:
        return CommandTransactionService(
            self.connection,
            now=lambda: NOW,
            checkpoint=checkpoint,
        )

    def _counts(self) -> tuple[int, int, int, int]:
        return (
            self.connection.execute(
                "SELECT COUNT(*) FROM plans WHERE id = ?",
                (str(self.plan_id),),
            ).fetchone()[0],
            self.connection.execute(
                "SELECT COUNT(*) FROM events WHERE aggregate_id = ?",
                (str(self.plan_id),),
            ).fetchone()[0],
            self.connection.execute(
                """
                SELECT COUNT(*)
                FROM outbox_events AS outbox
                JOIN events AS event ON event.id = outbox.event_id
                WHERE event.aggregate_id = ?
                """,
                (str(self.plan_id),),
            ).fetchone()[0],
            self.connection.execute(
                "SELECT COUNT(*) FROM command_log"
            ).fetchone()[0],
        )

    def _reopen(self) -> None:
        self.connection.close()
        self.connection = connect_database(self.database_path)

    def test_same_command_id_and_content_replays_without_side_effects(self) -> None:
        command = self._command()

        accepted = self._service().execute(command)
        self._reopen()
        replayed = self._service().execute(command)

        self.assertEqual(accepted.status, CommandStatus.ACCEPTED)
        self.assertEqual(replayed.status, CommandStatus.REPLAYED)
        self.assertEqual(
            replayed.affected_revisions,
            accepted.affected_revisions,
        )
        self.assertEqual(replayed.event_ids, accepted.event_ids)
        self.assertEqual(self._counts(), (2, 2, 2, 1))

    def test_same_command_id_with_different_content_is_conflict(self) -> None:
        command_id = uuid4()
        accepted = self._service().execute(
            self._command(command_id=command_id)
        )

        with self.assertRaises(CommandExecutionError) as raised:
            self._service().execute(
                self._command(command_id=command_id, title="Different")
            )

        self.assertEqual(
            raised.exception.error.code,
            ErrorCode.COMMAND_REPLAY_CONFLICT,
        )
        self.assertFalse(raised.exception.replayed)
        self.assertEqual(accepted.status, CommandStatus.ACCEPTED)
        self.assertEqual(self._counts(), (2, 2, 2, 1))

    def test_expected_revision_conflict_is_structured_and_idempotent(self) -> None:
        command = self._command(expected_revision=2)

        with self.assertRaises(CommandExecutionError) as first:
            self._service().execute(command)
        self._reopen()
        with self.assertRaises(CommandExecutionError) as replay:
            self._service().execute(command)

        self.assertEqual(first.exception.error.code, ErrorCode.REVISION_CONFLICT)
        self.assertEqual(
            first.exception.error.details,
            {
                "aggregate_type": "plan",
                "aggregate_id": str(self.plan_id),
                "expected_revision": 2,
                "actual_revision": 1,
            },
        )
        self.assertFalse(first.exception.replayed)
        self.assertTrue(replay.exception.replayed)
        self.assertEqual(self._counts(), (1, 1, 1, 1))
        row = self.connection.execute(
            "SELECT state, result_json, error_json FROM command_log"
        ).fetchone()
        self.assertEqual(row["state"], "rejected")
        self.assertIsNone(row["result_json"])
        self.assertIsNotNone(row["error_json"])

    def test_missing_plan_with_no_expected_revision_is_structured(self) -> None:
        missing_plan_id = uuid4()
        command = self._command(expected_revision=None).model_copy(
            update={"plan_id": missing_plan_id}
        )

        with self.assertRaises(CommandExecutionError) as raised:
            self._service().execute(command)

        self.assertEqual(
            raised.exception.error.code,
            ErrorCode.REVISION_CONFLICT,
        )
        self.assertEqual(
            raised.exception.error.details["aggregate_id"],
            str(missing_plan_id),
        )
        self.assertIsNone(
            raised.exception.error.details["actual_revision"]
        )
        self.assertEqual(self._counts(), (1, 1, 1, 1))

    def test_replay_requires_idle_connection(self) -> None:
        command = self._command()
        self._service().execute(command)
        self.connection.execute("BEGIN")
        try:
            with self.assertRaisesRegex(RuntimeError, "idle SQLite"):
                self._service().execute(command)
        finally:
            self.connection.rollback()

    def test_domain_event_outbox_and_result_commit_atomically(self) -> None:
        command = self._command()

        result = self._service().execute(command)

        self.assertEqual(self._counts(), (2, 2, 2, 1))
        self.assertEqual(
            result.affected_revisions,
            {f"plan:{self.plan_id}": 2},
        )
        event = self.connection.execute(
            """
            SELECT *
            FROM events
            WHERE aggregate_type = 'plan' AND aggregate_id = ?
            ORDER BY aggregate_version DESC
            LIMIT 1
            """,
            (str(self.plan_id),),
        ).fetchone()
        self.assertEqual(event["aggregate_version"], 2)
        self.assertEqual(event["type"], "plan.revised")
        self.assertEqual(event["causation_id"], str(command.command_id))
        self.assertEqual(
            json.loads(event["actor_json"]),
            command.actor.model_dump(mode="json"),
        )
        self.assertEqual(result.event_ids, (event["id"],))
        command_row = self.connection.execute(
            "SELECT * FROM command_log WHERE command_id = ?",
            (str(command.command_id),),
        ).fetchone()
        self.assertEqual(command_row["state"], "accepted")
        self.assertEqual(
            json.loads(command_row["result_json"])["event_ids"],
            [event["id"]],
        )

    def test_outbox_failure_rolls_back_domain_event_and_command_log(self) -> None:
        self.connection.execute(
            """
            CREATE TEMP TRIGGER fail_command_outbox
            BEFORE INSERT ON outbox_events
            BEGIN
                SELECT RAISE(ABORT, 'injected command outbox failure');
            END
            """
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "injected command outbox failure",
        ):
            self._service().execute(self._command())

        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self._counts(), (1, 1, 1, 0))

    def test_commit_time_failure_rolls_back_every_command_write(self) -> None:
        self.connection.execute("PRAGMA defer_foreign_keys = ON")
        self.connection.execute(
            """
            CREATE TEMP TRIGGER fail_command_commit
            AFTER INSERT ON command_log
            WHEN NEW.state = 'accepted'
            BEGIN
                INSERT INTO outbox_events(event_id) VALUES (9223372036854775807);
            END
            """
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self._service().execute(self._command())

        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self._counts(), (1, 1, 1, 0))

    def test_crash_before_commit_rolls_back_and_retry_applies_once(self) -> None:
        command = self._command()
        crash = CrashOnce("before_commit")

        with self.assertRaisesRegex(
            InjectedCommandCrash,
            "before_commit",
        ):
            self._service(crash).execute(command)

        self._reopen()
        self.assertEqual(self._counts(), (1, 1, 1, 0))
        accepted = self._service().execute(command)
        self.assertEqual(accepted.status, CommandStatus.ACCEPTED)
        self.assertEqual(self._counts(), (2, 2, 2, 1))
        self.assertTrue(crash.fired)

    def test_rejected_command_survives_after_commit_response_loss(self) -> None:
        command = self._command(expected_revision=2)
        crash = CrashOnce("after_commit")

        with self.assertRaisesRegex(
            InjectedCommandCrash,
            "after_commit",
        ):
            self._service(crash).execute(command)

        self._reopen()
        with self.assertRaises(CommandExecutionError) as replayed:
            self._service().execute(command)
        self.assertEqual(
            replayed.exception.error.code,
            ErrorCode.REVISION_CONFLICT,
        )
        self.assertTrue(replayed.exception.replayed)
        self.assertEqual(self._counts(), (1, 1, 1, 1))
        self.assertTrue(crash.fired)

    def test_crash_after_commit_replays_without_event_loss(self) -> None:
        command = self._command()
        crash = CrashOnce("after_commit")

        with self.assertRaisesRegex(
            InjectedCommandCrash,
            "after_commit",
        ):
            self._service(crash).execute(command)

        self._reopen()
        self.assertEqual(self._counts(), (2, 2, 2, 1))
        replayed = self._service().execute(command)
        self.assertEqual(replayed.status, CommandStatus.REPLAYED)
        self.assertEqual(self._counts(), (2, 2, 2, 1))
        self.assertTrue(crash.fired)

    def test_request_hash_is_stable_across_mapping_key_order(self) -> None:
        command_id = uuid4()
        first = self._command(command_id=command_id).model_copy(
            update={"policy": {"alpha": 1, "beta": 2}}
        )
        same_content = self._command(command_id=command_id).model_copy(
            update={"policy": {"beta": 2, "alpha": 1}}
        )

        accepted = self._service().execute(first)
        replayed = self._service().execute(same_content)

        self.assertEqual(accepted.status, CommandStatus.ACCEPTED)
        self.assertEqual(replayed.status, CommandStatus.REPLAYED)
        self.assertEqual(self._counts(), (2, 2, 2, 1))

    def test_replay_fails_closed_when_stored_result_is_not_bound(self) -> None:
        command = self._command()
        accepted = self._service().execute(command)
        original = accepted.model_dump(mode="json")
        corrupt_results = (
            {
                **original,
                "command_id": str(uuid4()),
            },
            {
                **original,
                "event_ids": [1],
            },
        )

        for corrupt in corrupt_results:
            with self.subTest(corrupt=corrupt):
                self.connection.execute(
                    """
                    UPDATE command_log
                    SET result_json = ?
                    WHERE command_id = ?
                    """,
                    (_json(corrupt), str(command.command_id)),
                )
                self.connection.commit()
                with self.assertRaisesRegex(
                    RuntimeError,
                    "stored CommandResult",
                ):
                    self._service().execute(command)

    def test_rejected_replay_fails_closed_when_error_is_not_bound(self) -> None:
        command = self._command(expected_revision=2)
        with self.assertRaises(CommandExecutionError):
            self._service().execute(command)
        row = self.connection.execute(
            "SELECT error_json FROM command_log WHERE command_id = ?",
            (str(command.command_id),),
        ).fetchone()
        corrupt = json.loads(str(row["error_json"]))
        corrupt["details"]["aggregate_id"] = str(uuid4())
        self.connection.execute(
            """
            UPDATE command_log
            SET error_json = ?
            WHERE command_id = ?
            """,
            (_json(corrupt), str(command.command_id)),
        )
        self.connection.commit()

        with self.assertRaisesRegex(
            RuntimeError,
            "stored Command rejection",
        ):
            self._service().execute(command)

    def test_two_connections_racing_same_id_apply_once(self) -> None:
        command = self._command()
        first_before_commit = threading.Event()
        release_first = threading.Event()
        second_prechecked = threading.Event()
        results = []
        errors: list[BaseException] = []

        def run_first() -> None:
            connection = connect_database(self.database_path)
            try:
                def checkpoint(name: str) -> None:
                    if name == "before_commit":
                        first_before_commit.set()
                        if not release_first.wait(5):
                            raise TimeoutError("first command was not released")

                results.append(
                    CommandTransactionService(
                        connection,
                        now=lambda: NOW,
                        checkpoint=checkpoint,
                    ).execute(command)
                )
            except BaseException as exc:
                errors.append(exc)
            finally:
                connection.close()

        def run_second() -> None:
            connection = connect_database(self.database_path)
            try:
                def trace(statement: str) -> None:
                    if (
                        "FROM command_log" in statement
                        and "SELECT type" in statement
                    ):
                        second_prechecked.set()

                connection.set_trace_callback(trace)
                results.append(
                    CommandTransactionService(
                        connection,
                        now=lambda: NOW,
                    ).execute(command)
                )
            except BaseException as exc:
                errors.append(exc)
            finally:
                connection.close()

        first_thread = threading.Thread(target=run_first)
        second_thread = threading.Thread(target=run_second)
        first_thread.start()
        try:
            self.assertTrue(first_before_commit.wait(5))
            second_thread.start()
            self.assertTrue(second_prechecked.wait(5))
        finally:
            release_first.set()
        first_thread.join(5)
        second_thread.join(5)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(
            {result.status for result in results},
            {CommandStatus.ACCEPTED, CommandStatus.REPLAYED},
        )
        self.assertEqual(self._counts(), (2, 2, 2, 1))


if __name__ == "__main__":
    unittest.main()
