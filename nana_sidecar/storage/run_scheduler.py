"""D2-01 durable scheduler admission and cancel state transitions.

This module does not authorize Actions, consume approvals/grants, spawn child
processes, or produce receipts. It only moves already-authorized state through
the canonical SQLite Event/outbox boundary.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Callable, Iterator

from nana_sidecar.contracts.common import ActorRef
from nana_sidecar.storage.budget_accounting import (
    BudgetAccountingError,
    BudgetAccountingService,
)


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class SchedulerStateError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SchedulerResult:
    kind: str
    run_id: str
    action_id: str | None
    event_ids: tuple[int, ...]


class RunSchedulerService:
    """Claim Actions and cancel Runs in SQLite transactions."""

    _terminal_run_states = frozenset(
        {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "budget_exceeded",
            "orphaned",
        }
    )
    _pending_action_states = frozenset(
        {"proposed", "waiting_approval", "authorized"}
    )

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        now: Callable[[], str],
    ) -> None:
        self.connection = connection
        self._now = now

    def claim_action(
        self,
        *,
        run_id: str,
        action_id: str,
        actor: ActorRef,
        causation_id: str | None = None,
    ) -> SchedulerResult:
        self._require_idle()
        with self._transaction():
            run = self._require_run(run_id)
            self._require_runnable_run(run)
            action = self._require_action(action_id)
            if str(action["run_id"]) != run_id:
                raise SchedulerStateError(
                    "E_ACTION_RUN_MISMATCH",
                    "Action does not belong to Run",
                )
            if str(action["state"]) != "authorized":
                raise SchedulerStateError(
                    "E_ACTION_NOT_AUTHORIZED",
                    "Action is not authorized for scheduler claim",
                )
            self._require_grant_concurrency_slot(action_id)
            budget = BudgetAccountingService(self.connection, now=self._now)
            try:
                budget_result = budget.reserve_action_start(
                    run_id=run_id,
                    actor=actor,
                    causation_id=causation_id,
                )
            except BudgetAccountingError as exc:
                raise SchedulerStateError(exc.code, str(exc)) from exc
            if budget_result.kind == "concurrency_limited":
                raise SchedulerStateError(
                    "E_RUN_CONCURRENCY_LIMIT",
                    "Run has reached its max_concurrency budget",
                )
            if budget_result.kind == "exhausted":
                event_id = self._finish_run(
                    run_id=run_id,
                    state="budget_exceeded",
                    event_type="run.budget_exceeded",
                    actor=actor,
                    reason=budget_result.reason or "budget_exhausted",
                    causation_id=causation_id,
                )
                return SchedulerResult(
                    kind="budget_exceeded",
                    run_id=run_id,
                    action_id=None,
                    event_ids=budget_result.event_ids + (event_id,),
                )
            if budget_result.kind != "reserved":
                raise SchedulerStateError(
                    "E_RUN_BUDGET_INVALID",
                    "Budget reserve returned an unknown outcome",
                )

            occurred_at = self._now()
            updated = self.connection.execute(
                """
                UPDATE actions
                SET state = 'running', started_at = ?
                WHERE id = ? AND run_id = ? AND state = 'authorized'
                """,
                (occurred_at, action_id, run_id),
            )
            if updated.rowcount != 1:
                raise SchedulerStateError(
                    "E_ACTION_CLAIM_RACE",
                    "Action was claimed or changed before this scheduler claim",
                )
            event_id = self._append_event(
                aggregate_type="action",
                aggregate_id=action_id,
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                event_type="action.started",
                payload={
                    "action_id": action_id,
                    "previous_state": "authorized",
                    "state": "running",
                },
                occurred_at=occurred_at,
                causation_id=causation_id,
            )
            return SchedulerResult(
                kind="claimed",
                run_id=run_id,
                action_id=action_id,
                event_ids=budget_result.event_ids + (event_id,),
            )

    def cancel_run(
        self,
        *,
        run_id: str,
        actor: ActorRef,
        reason: str,
        causation_id: str | None = None,
        _in_transaction: bool = False,
    ) -> SchedulerResult:
        if not reason.strip():
            raise ValueError("cancel reason is required")
        if not _in_transaction:
            self._require_idle()
        transaction = nullcontext() if _in_transaction else self._transaction()
        with transaction:
            run = self._require_run(run_id)
            if str(run["state"]) in self._terminal_run_states:
                return SchedulerResult(
                    kind="already_terminal",
                    run_id=run_id,
                    action_id=None,
                    event_ids=(),
                )
            if str(run["state"]) == "paused":
                try:
                    result = json.loads(str(run["result_json"] or "{}"))
                except json.JSONDecodeError:
                    result = {}
                if result.get("reason") == "cancel_requested":
                    return SchedulerResult(
                        kind="cancellation_requested",
                        run_id=run_id,
                        action_id=None,
                        event_ids=(),
                    )
            occurred_at = self._now()
            actions = self.connection.execute(
                """
                SELECT id, state
                FROM actions
                WHERE run_id = ?
                  AND state IN (
                      'proposed', 'waiting_approval', 'authorized', 'running'
                  )
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()
            has_running = any(str(action["state"]) == "running" for action in actions)
            if has_running:
                run_event_id = self._pause_run_for_cancel(
                    run_id=run_id,
                    actor=actor,
                    reason=reason,
                    causation_id=causation_id,
                )
                result_kind = "cancellation_requested"
            else:
                run_event_id = self._finish_run(
                    run_id=run_id,
                    state="cancelled",
                    event_type="run.cancelled",
                    actor=actor,
                    reason=reason,
                    causation_id=causation_id,
                )
                result_kind = "cancelled"
            event_ids: list[int] = [run_event_id]
            for action in actions:
                action_id = str(action["id"])
                previous_state = str(action["state"])
                if previous_state == "running":
                    continue
                next_state = "cancelled"
                event_type = "action.cancelled"
                event_reason = "run_cancelled"
                updated = self.connection.execute(
                    """
                    UPDATE actions
                    SET state = ?, finished_at = ?
                    WHERE id = ? AND state = ?
                    """,
                    (next_state, occurred_at, action_id, previous_state),
                )
                if updated.rowcount != 1:
                    raise SchedulerStateError(
                        "E_ACTION_CANCEL_RACE",
                        "Action changed before cancellation could be recorded",
                    )
                event_ids.append(
                    self._append_event(
                        aggregate_type="action",
                        aggregate_id=action_id,
                        run_id=run_id,
                        action_id=action_id,
                        actor=actor,
                        event_type=event_type,
                        payload={
                            "action_id": action_id,
                            "previous_state": previous_state,
                            "state": next_state,
                            "reason": event_reason,
                        },
                        occurred_at=occurred_at,
                        causation_id=causation_id,
                    )
                )
            return SchedulerResult(
                kind=result_kind,
                run_id=run_id,
                action_id=None,
                event_ids=tuple(event_ids),
            )

    def pause_run(
        self,
        *,
        run_id: str,
        actor: ActorRef,
        reason: str,
        causation_id: str | None = None,
        _in_transaction: bool = False,
    ) -> SchedulerResult:
        if not reason.strip():
            raise ValueError("pause reason is required")
        if not _in_transaction:
            self._require_idle()
        transaction = nullcontext() if _in_transaction else self._transaction()
        with transaction:
            run = self._require_run(run_id)
            state = str(run["state"])
            if state != "running":
                raise SchedulerStateError(
                    "E_RUN_PAUSE_STATE", "only a running Run can be paused"
                )
            occurred_at = self._now()
            result = {"state": "paused", "reason": "user_paused", "detail": reason}
            updated = self.connection.execute(
                "UPDATE runs SET state = 'paused', result_json = ? WHERE id = ? AND state = 'running'",
                (_json(result), run_id),
            )
            if updated.rowcount != 1:
                raise SchedulerStateError("E_RUN_PAUSE_RACE", "Run changed before pause")
            event_id = self._append_event(
                aggregate_type="run", aggregate_id=run_id, run_id=run_id,
                action_id=None, actor=actor, event_type="run.paused",
                payload={"run_id": run_id, **result}, occurred_at=occurred_at,
                causation_id=causation_id,
            )
            return SchedulerResult("paused", run_id, None, (event_id,))

    def resume_run(
        self,
        *,
        run_id: str,
        actor: ActorRef,
        reason: str,
        causation_id: str | None = None,
        _in_transaction: bool = False,
    ) -> SchedulerResult:
        if not reason.strip():
            raise ValueError("resume reason is required")
        if not _in_transaction:
            self._require_idle()
        transaction = nullcontext() if _in_transaction else self._transaction()
        with transaction:
            run = self._require_run(run_id)
            state = str(run["state"])
            try:
                prior = json.loads(str(run["result_json"] or "{}"))
            except json.JSONDecodeError:
                prior = {}
            if state != "paused" or prior.get("reason") != "user_paused":
                raise SchedulerStateError(
                    "E_RUN_RESUME_STATE",
                    f"only a user-paused Run can be resumed (state={state}, reason={prior.get('reason')})",
                )
            occurred_at = self._now()
            result = {"state": "running", "reason": "user_resumed", "detail": reason}
            updated = self.connection.execute(
                "UPDATE runs SET state = 'running', result_json = ? WHERE id = ? AND state = 'paused'",
                (_json(result), run_id),
            )
            if updated.rowcount != 1:
                raise SchedulerStateError("E_RUN_RESUME_RACE", "Run changed before resume")
            event_id = self._append_event(
                aggregate_type="run", aggregate_id=run_id, run_id=run_id,
                action_id=None, actor=actor, event_type="run.started",
                payload={"run_id": run_id, **result}, occurred_at=occurred_at,
                causation_id=causation_id,
            )
            return SchedulerResult("resumed", run_id, None, (event_id,))

    def _pause_run_for_cancel(
        self,
        *,
        run_id: str,
        actor: ActorRef,
        reason: str,
        causation_id: str | None,
    ) -> int:
        occurred_at = self._now()
        updated = self.connection.execute(
            """
            UPDATE runs
            SET state = 'paused', result_json = ?
            WHERE id = ? AND state = 'running'
            """,
            (_json({"reason": "cancel_requested", "detail": reason}), run_id),
        )
        if updated.rowcount != 1:
            raise SchedulerStateError(
                "E_RUN_CANCEL_RACE",
                "Run changed before cancellation could be requested",
            )
        return self._append_event(
            aggregate_type="run",
            aggregate_id=run_id,
            run_id=run_id,
            action_id=None,
            actor=actor,
            event_type="run.paused",
            payload={
                "run_id": run_id,
                "state": "paused",
                "reason": "cancel_requested",
                "detail": reason,
            },
            occurred_at=occurred_at,
            causation_id=causation_id,
        )

    def _require_grant_concurrency_slot(self, action_id: str) -> None:
        authorization = self.connection.execute(
            """
            SELECT authorization_source, authorization_ref
            FROM action_authorizations
            WHERE action_id = ?
            """,
            (action_id,),
        ).fetchone()
        if authorization is None:
            action = self.connection.execute(
                "SELECT authorization_ref FROM actions WHERE id = ?",
                (action_id,),
            ).fetchone()
            if action is not None and not str(action["authorization_ref"] or "").startswith(
                "policy_grant:"
            ):
                return
            raise SchedulerStateError(
                "E_ACTION_AUTHORIZATION_MISSING",
                "Authorized Action has no durable authorization material",
            )
        if str(authorization["authorization_source"]) != "policy_grant":
            return
        authorization_ref = str(authorization["authorization_ref"])
        grant_id = authorization_ref.removeprefix("policy_grant:")
        if not authorization_ref.startswith("policy_grant:") or not grant_id:
            raise SchedulerStateError(
                "E_ACTION_AUTHORIZATION_INVALID",
                "PolicyGrant authorization reference is invalid",
            )
        grant = self.connection.execute(
            "SELECT constraints_json, state FROM policy_grants WHERE id = ?",
            (grant_id,),
        ).fetchone()
        if grant is None:
            raise SchedulerStateError(
                "E_POLICY_GRANT_NOT_FOUND",
                "Authorizing PolicyGrant no longer exists",
            )
        try:
            constraints = json.loads(str(grant["constraints_json"]))
            max_concurrency = int(constraints["max_concurrency"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SchedulerStateError(
                "E_POLICY_GRANT_INVALID",
                "Authorizing PolicyGrant constraints are invalid",
            ) from exc
        running = int(
            self.connection.execute(
                """
                SELECT COUNT(*)
                FROM actions
                JOIN action_authorizations
                  ON action_authorizations.action_id = actions.id
                WHERE action_authorizations.authorization_source = 'policy_grant'
                  AND action_authorizations.authorization_ref = ?
                  AND actions.state = 'running'
                  AND actions.id <> ?
                """,
                (authorization_ref, action_id),
            ).fetchone()[0]
        )
        if running >= max_concurrency:
            raise SchedulerStateError(
                "E_POLICY_GRANT_CONCURRENCY_LIMIT",
                "PolicyGrant has reached its max_concurrency limit",
            )

    def _finish_run(
        self,
        *,
        run_id: str,
        state: str,
        event_type: str,
        actor: ActorRef,
        reason: str,
        causation_id: str | None,
    ) -> int:
        occurred_at = self._now()
        updated = self.connection.execute(
            """
            UPDATE runs
            SET state = ?, finished_at = ?, result_json = ?
            WHERE id = ?
              AND state NOT IN (
                  'succeeded', 'failed', 'cancelled', 'timed_out',
                  'budget_exceeded', 'orphaned'
              )
            """,
            (
                state,
                occurred_at,
                _json({"reason": reason, "state": state}),
                run_id,
            ),
        )
        if updated.rowcount != 1:
            raise SchedulerStateError(
                "E_RUN_FINISH_RACE",
                "Run became terminal before scheduler transition",
            )
        return self._append_event(
            aggregate_type="run",
            aggregate_id=run_id,
            run_id=run_id,
            action_id=None,
            actor=actor,
            event_type=event_type,
            payload={"run_id": run_id, "state": state, "reason": reason},
            occurred_at=occurred_at,
            causation_id=causation_id,
        )

    def _append_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        run_id: str,
        action_id: str | None,
        actor: ActorRef,
        event_type: str,
        payload: object,
        occurred_at: str,
        causation_id: str | None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version,
                run_id, run_seq, action_id, actor_json, causation_id,
                type, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aggregate_type,
                aggregate_id,
                self._next_aggregate_version(aggregate_type, aggregate_id),
                run_id,
                self._next_run_seq(run_id),
                action_id,
                _json(actor.model_dump(mode="json")),
                causation_id,
                event_type,
                _json(payload),
                occurred_at,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (event_id,),
        )
        return event_id

    def _require_run(self, run_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT id, state, snapshot_json, result_json FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise SchedulerStateError("E_RUN_NOT_FOUND", "Run does not exist")
        return row

    def _require_runnable_run(self, run: sqlite3.Row) -> None:
        if str(run["state"]) != "running":
            raise SchedulerStateError(
                "E_RUN_NOT_RUNNING",
                "Run is not running and cannot claim Actions",
            )

    def _require_action(self, action_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT id, run_id, state FROM actions WHERE id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise SchedulerStateError(
                "E_ACTION_NOT_FOUND",
                "Action does not exist",
            )
        return row

    def _next_aggregate_version(
        self,
        aggregate_type: str,
        aggregate_id: str,
    ) -> int:
        current = self.connection.execute(
            """
            SELECT COALESCE(MAX(aggregate_version), 0)
            FROM events
            WHERE aggregate_type = ? AND aggregate_id = ?
            """,
            (aggregate_type, aggregate_id),
        ).fetchone()[0]
        return int(current) + 1

    def _next_run_seq(self, run_id: str) -> int:
        current = self.connection.execute(
            """
            SELECT COALESCE(MAX(run_seq), 0)
            FROM events
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]
        return int(current) + 1

    def _require_idle(self) -> None:
        if self.connection.in_transaction:
            raise SchedulerStateError(
                "E_TRANSACTION_ACTIVE",
                "Scheduler requires an idle SQLite connection",
            )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        else:
            self.connection.commit()
