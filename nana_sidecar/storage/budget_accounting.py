"""D2-05 runtime budget accounting for durable Run execution."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Callable

from nana_sidecar.contracts.common import ActorRef, BudgetSnapshot, ResourceUsage


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class BudgetAccountingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class BudgetAccountingResult:
    kind: str
    run_id: str
    reason: str | None
    event_ids: tuple[int, ...]


class BudgetAccountingService:
    """Maintain Run budget ledger rows inside caller-owned SQLite transactions."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        now: Callable[[], str],
    ) -> None:
        self.connection = connection
        self._now = now

    def reserve_action_start(
        self,
        *,
        run_id: str,
        actor: ActorRef,
        causation_id: str | None = None,
    ) -> BudgetAccountingResult:
        self._require_active_transaction()
        row = self._ensure_ledger(run_id)
        limits = self._limits(row)
        if int(row["exhausted"]) == 1:
            return BudgetAccountingResult(
                kind="exhausted",
                run_id=run_id,
                reason=str(row["exhausted_reason"]),
                event_ids=(),
            )
        usage_reason = self._exhaustion_reason(limits, self._usage(row))
        if usage_reason is not None:
            return self._mark_exhausted(
                row=row,
                actor=actor,
                reason=usage_reason,
                action_id=None,
                causation_id=causation_id,
            )
        started_actions = int(row["started_actions"])
        running_actions = int(row["running_actions"])
        if started_actions >= limits.max_actions:
            return self._mark_exhausted(
                row=row,
                actor=actor,
                reason="max_actions_exhausted",
                action_id=None,
                causation_id=causation_id,
            )
        if running_actions >= limits.max_concurrency:
            return BudgetAccountingResult(
                kind="concurrency_limited",
                run_id=run_id,
                reason="max_concurrency_reached",
                event_ids=(),
            )

        occurred_at = self._now()
        started_actions += 1
        running_actions += 1
        self.connection.execute(
            """
            UPDATE run_budget_ledger
            SET started_actions = ?,
                running_actions = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (started_actions, running_actions, occurred_at, run_id),
        )
        event_id = self._append_event(
            aggregate_type="budget",
            aggregate_id=run_id,
            run_id=run_id,
            action_id=None,
            actor=actor,
            event_type="budget.updated",
            payload={
                "run_id": run_id,
                "reason": "action_start_reserved",
                "started_actions": started_actions,
                "running_actions": running_actions,
                "usage": self._usage(row).model_dump(mode="json"),
                "limits": limits.model_dump(mode="json"),
            },
            occurred_at=occurred_at,
            causation_id=causation_id,
        )
        return BudgetAccountingResult(
            kind="reserved",
            run_id=run_id,
            reason=None,
            event_ids=(event_id,),
        )

    def record_action_usage(
        self,
        *,
        run_id: str,
        action_id: str,
        usage: ResourceUsage,
        actor: ActorRef,
        causation_id: str | None = None,
    ) -> BudgetAccountingResult:
        self._require_active_transaction()
        row = self._ensure_ledger(run_id)
        limits = self._limits(row)
        current_usage = self._usage(row)
        running_actions = int(row["running_actions"])
        if running_actions < 1:
            raise BudgetAccountingError(
                "E_BUDGET_RUNNING_UNDERFLOW",
                "Cannot record action usage without a matching start reservation",
            )
        next_usage = self._add_usage(current_usage, usage)
        next_running = running_actions - 1
        occurred_at = self._now()
        previous_exhausted = int(row["exhausted"]) == 1
        reason = (
            str(row["exhausted_reason"])
            if previous_exhausted
            else self._exhaustion_reason(limits, next_usage)
        )
        exhausted = previous_exhausted or reason is not None
        self.connection.execute(
            """
            UPDATE run_budget_ledger
            SET usage_json = ?,
                running_actions = ?,
                exhausted = ?,
                exhausted_reason = ?,
                exhausted_at = CASE
                    WHEN exhausted = 0 AND ? = 1 THEN ?
                    ELSE exhausted_at
                END,
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                _json(next_usage.model_dump(mode="json")),
                next_running,
                1 if exhausted else 0,
                reason,
                1 if exhausted else 0,
                occurred_at,
                occurred_at,
                run_id,
            ),
        )
        event_ids: list[int] = [
            self._append_event(
                aggregate_type="budget",
                aggregate_id=run_id,
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                event_type="budget.updated",
                payload={
                    "run_id": run_id,
                    "action_id": action_id,
                    "reason": "action_usage_recorded",
                    "started_actions": int(row["started_actions"]),
                    "running_actions": next_running,
                    "usage": next_usage.model_dump(mode="json"),
                    "limits": limits.model_dump(mode="json"),
                },
                occurred_at=occurred_at,
                causation_id=causation_id,
            )
        ]
        if exhausted and not previous_exhausted:
            event_ids.append(
                self._append_event(
                    aggregate_type="budget",
                    aggregate_id=run_id,
                    run_id=run_id,
                    action_id=action_id,
                    actor=actor,
                    event_type="budget.threshold_reached",
                    payload={
                        "run_id": run_id,
                        "action_id": action_id,
                        "reason": reason,
                        "usage": next_usage.model_dump(mode="json"),
                        "limits": limits.model_dump(mode="json"),
                    },
                    occurred_at=occurred_at,
                    causation_id=causation_id,
                )
            )
        return BudgetAccountingResult(
            kind="exhausted" if exhausted else "recorded",
            run_id=run_id,
            reason=reason,
            event_ids=tuple(event_ids),
        )

    def _mark_exhausted(
        self,
        *,
        row: sqlite3.Row,
        actor: ActorRef,
        reason: str,
        action_id: str | None,
        causation_id: str | None,
    ) -> BudgetAccountingResult:
        run_id = str(row["run_id"])
        occurred_at = self._now()
        self.connection.execute(
            """
            UPDATE run_budget_ledger
            SET exhausted = 1,
                exhausted_reason = ?,
                exhausted_at = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (reason, occurred_at, occurred_at, run_id),
        )
        event_id = self._append_event(
            aggregate_type="budget",
            aggregate_id=run_id,
            run_id=run_id,
            action_id=action_id,
            actor=actor,
            event_type="budget.threshold_reached",
            payload={
                "run_id": run_id,
                "action_id": action_id,
                "reason": reason,
                "started_actions": int(row["started_actions"]),
                "running_actions": int(row["running_actions"]),
                "usage": self._usage(row).model_dump(mode="json"),
                "limits": self._limits(row).model_dump(mode="json"),
            },
            occurred_at=occurred_at,
            causation_id=causation_id,
        )
        return BudgetAccountingResult(
            kind="exhausted",
            run_id=run_id,
            reason=reason,
            event_ids=(event_id,),
        )

    def _ensure_ledger(self, run_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT run_id, limits_json, usage_json, started_actions,
                   running_actions, exhausted, exhausted_reason, exhausted_at,
                   updated_at
            FROM run_budget_ledger
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is not None:
            return row
        run = self.connection.execute(
            "SELECT id, snapshot_json FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise BudgetAccountingError("E_RUN_NOT_FOUND", "Run does not exist")
        try:
            snapshot = json.loads(str(run["snapshot_json"]))
            limits = BudgetSnapshot.model_validate(snapshot["budget"])
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise BudgetAccountingError(
                "E_RUN_BUDGET_INVALID",
                "Run snapshot does not contain a valid budget",
            ) from exc
        usage = self._usage_from_existing_receipts(run_id)
        counts = self.connection.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE started_at IS NOT NULL) AS started_actions,
                COUNT(*) FILTER (WHERE state = 'running') AS running_actions
            FROM actions
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        started_actions = int(counts["started_actions"])
        running_actions = int(counts["running_actions"])
        now = self._now()
        self.connection.execute(
            """
            INSERT INTO run_budget_ledger (
                run_id, limits_json, usage_json, started_actions,
                running_actions, exhausted, exhausted_reason, exhausted_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, NULL, NULL, ?)
            """,
            (
                run_id,
                _json(limits.model_dump(mode="json")),
                _json(usage.model_dump(mode="json")),
                started_actions,
                running_actions,
                now,
            ),
        )
        return self.connection.execute(
            """
            SELECT run_id, limits_json, usage_json, started_actions,
                   running_actions, exhausted, exhausted_reason, exhausted_at,
                   updated_at
            FROM run_budget_ledger
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

    def _usage_from_existing_receipts(self, run_id: str) -> ResourceUsage:
        usage = ResourceUsage(wall_clock_ms=0)
        rows = self.connection.execute(
            """
            SELECT action_receipts.resource_usage_json
            FROM action_receipts
            JOIN actions ON actions.id = action_receipts.action_id
            WHERE actions.run_id = ?
            ORDER BY action_receipts.id
            """,
            (run_id,),
        ).fetchall()
        for row in rows:
            try:
                delta = ResourceUsage.model_validate(
                    json.loads(str(row["resource_usage_json"]))
                )
            except (TypeError, json.JSONDecodeError, ValueError) as exc:
                raise BudgetAccountingError(
                    "E_BUDGET_LEDGER_INVALID",
                    "Existing action receipt usage is invalid",
                ) from exc
            usage = self._add_usage(usage, delta)
        return usage

    def _limits(self, row: sqlite3.Row) -> BudgetSnapshot:
        try:
            return BudgetSnapshot.model_validate(json.loads(str(row["limits_json"])))
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            raise BudgetAccountingError(
                "E_BUDGET_LEDGER_INVALID",
                "Budget ledger limits are invalid",
            ) from exc

    def _usage(self, row: sqlite3.Row) -> ResourceUsage:
        try:
            return ResourceUsage.model_validate(json.loads(str(row["usage_json"])))
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            raise BudgetAccountingError(
                "E_BUDGET_LEDGER_INVALID",
                "Budget ledger usage is invalid",
            ) from exc

    def _add_usage(
        self,
        current: ResourceUsage,
        delta: ResourceUsage,
    ) -> ResourceUsage:
        return ResourceUsage(
            wall_clock_ms=current.wall_clock_ms + delta.wall_clock_ms,
            cpu_ms=self._add_optional(current.cpu_ms, delta.cpu_ms),
            peak_memory_bytes=max(
                current.peak_memory_bytes or 0,
                delta.peak_memory_bytes or 0,
            )
            or None,
            model_tokens=current.model_tokens + delta.model_tokens,
            cost_micros=current.cost_micros + delta.cost_micros,
            output_bytes=current.output_bytes + delta.output_bytes,
            artifact_bytes=current.artifact_bytes + delta.artifact_bytes,
        )

    def _exhaustion_reason(
        self,
        limits: BudgetSnapshot,
        usage: ResourceUsage,
    ) -> str | None:
        if usage.wall_clock_ms >= limits.wall_clock_seconds * 1000:
            return "wall_clock_exhausted"
        if (
            limits.cpu_seconds is not None
            and usage.cpu_ms is not None
            and usage.cpu_ms >= limits.cpu_seconds * 1000
        ):
            return "cpu_exhausted"
        if (
            limits.memory_bytes is not None
            and usage.peak_memory_bytes is not None
            and usage.peak_memory_bytes >= limits.memory_bytes
        ):
            return "memory_exhausted"
        if usage.output_bytes >= limits.max_output_bytes:
            return "output_bytes_exhausted"
        if usage.artifact_bytes >= limits.max_artifact_bytes:
            return "artifact_bytes_exhausted"
        if limits.max_model_tokens == 0:
            if usage.model_tokens > 0:
                return "model_tokens_exhausted"
        elif usage.model_tokens >= limits.max_model_tokens:
            return "model_tokens_exhausted"
        if limits.max_cost_micros == 0:
            if usage.cost_micros > 0:
                return "cost_exhausted"
        elif usage.cost_micros >= limits.max_cost_micros:
            return "cost_exhausted"
        return None

    @staticmethod
    def _add_optional(first: int | None, second: int | None) -> int | None:
        if first is None and second is None:
            return None
        return (first or 0) + (second or 0)

    def _append_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        run_id: str,
        action_id: str | None,
        actor: ActorRef,
        event_type: str,
        payload: dict[str, object],
        occurred_at: str,
        causation_id: str | None,
    ) -> int:
        aggregate_version = self._next_aggregate_version(
            aggregate_type,
            aggregate_id,
        )
        payload = dict(payload)
        payload["sequence"] = aggregate_version
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
                aggregate_version,
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

    def _require_active_transaction(self) -> None:
        if not self.connection.in_transaction:
            raise BudgetAccountingError(
                "E_BUDGET_TRANSACTION_REQUIRED",
                "Budget accounting must run inside the caller's SQLite transaction",
            )
