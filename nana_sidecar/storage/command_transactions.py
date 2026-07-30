"""D1 Command idempotency and domain/Event/outbox transaction runtime."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from typing import Callable, Iterator

from nana_sidecar.contracts.commands import (
    CommandResult,
    CommandStatus,
    RevisePlan,
)
from nana_sidecar.contracts.errors import (
    ErrorCategory,
    ErrorCode,
    StructuredError,
)


def _no_checkpoint(name: str) -> None:
    return None


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class CommandExecutionError(RuntimeError):
    """A structured, optionally replayed Command rejection."""

    def __init__(
        self,
        error: StructuredError,
        *,
        replayed: bool = False,
    ) -> None:
        super().__init__(error.message)
        self.error = error
        self.replayed = replayed


class CommandTransactionService:
    """Execute the D1-05 revisioned Plan command in one SQLite transaction."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        now: Callable[[], str],
        checkpoint: Callable[[str], None] | None = None,
    ) -> None:
        self.connection = connection
        self._now = now
        self._checkpoint = checkpoint or _no_checkpoint

    def execute(self, command: RevisePlan) -> CommandResult:
        if not isinstance(command, RevisePlan):
            raise TypeError("D1-05 Command runtime supports RevisePlan")
        self._require_idle()
        request_hash = self._request_hash(command)
        existing = self._find_command(command)
        if existing is not None:
            return self._replay(existing, command, request_hash)

        result: CommandResult | None = None
        rejection: StructuredError | None = None
        replayed_result: CommandResult | None = None
        with self._transaction():
            existing = self._find_command(command)
            if existing is not None:
                replayed_result = self._replay(
                    existing,
                    command,
                    request_hash,
                )
            else:
                current = self.connection.execute(
                    """
                    SELECT inquiry_id, revision
                    FROM plans
                    WHERE id = ?
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (str(command.plan_id),),
                ).fetchone()
                actual_revision = (
                    int(current["revision"])
                    if current is not None
                    else None
                )
                if (
                    current is None
                    or command.expected_revision != actual_revision
                ):
                    rejection = self._revision_conflict(
                        command,
                        actual_revision,
                    )
                    self._insert_rejected_command(
                        command,
                        request_hash,
                        rejection,
                    )
                else:
                    result = self._revise_plan(
                        command,
                        request_hash,
                        inquiry_id=str(current["inquiry_id"]),
                        current_revision=actual_revision,
                    )
                self._checkpoint("before_commit")

        if replayed_result is not None:
            return replayed_result
        self._checkpoint("after_commit")
        if rejection is not None:
            raise CommandExecutionError(rejection)
        if result is None:
            raise RuntimeError("Command transaction produced no result")
        return result

    def _revise_plan(
        self,
        command: RevisePlan,
        request_hash: str,
        *,
        inquiry_id: str,
        current_revision: int,
    ) -> CommandResult:
        new_revision = current_revision + 1
        occurred_at = self._now()
        self.connection.execute(
            """
            INSERT INTO plans (
                id, inquiry_id, revision, status, steps_json, policy_json,
                budget_json, created_at
            ) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (
                str(command.plan_id),
                inquiry_id,
                new_revision,
                _json(
                    [
                        step.model_dump(mode="json")
                        for step in command.steps
                    ]
                ),
                _json(command.policy),
                _json(command.budget.model_dump(mode="json")),
                occurred_at,
            ),
        )
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                causation_id, type, payload_json, occurred_at
            ) VALUES ('plan', ?, ?, ?, ?, 'plan.revised', ?, ?)
            """,
            (
                str(command.plan_id),
                new_revision,
                _json(command.actor.model_dump(mode="json")),
                str(command.command_id),
                _json(
                    {
                        "plan_id": str(command.plan_id),
                        "previous_revision": current_revision,
                        "revision": new_revision,
                        "status": "draft",
                    }
                ),
                occurred_at,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (event_id,),
        )
        result = CommandResult(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            affected_revisions={
                f"plan:{command.plan_id}": new_revision,
            },
            event_ids=(event_id,),
        )
        self.connection.execute(
            """
            INSERT INTO command_log (
                command_id, type, request_hash, actor_json, state,
                result_json, created_at, finished_at
            ) VALUES (?, ?, ?, ?, 'accepted', ?, ?, ?)
            """,
            (
                str(command.command_id),
                command.type,
                request_hash,
                _json(command.actor.model_dump(mode="json")),
                _json(result.model_dump(mode="json")),
                occurred_at,
                occurred_at,
            ),
        )
        return result

    def _insert_rejected_command(
        self,
        command: RevisePlan,
        request_hash: str,
        error: StructuredError,
    ) -> None:
        occurred_at = self._now()
        self.connection.execute(
            """
            INSERT INTO command_log (
                command_id, type, request_hash, actor_json, state,
                error_json, created_at, finished_at
            ) VALUES (?, ?, ?, ?, 'rejected', ?, ?, ?)
            """,
            (
                str(command.command_id),
                command.type,
                request_hash,
                _json(command.actor.model_dump(mode="json")),
                _json(error.model_dump(mode="json")),
                occurred_at,
                occurred_at,
            ),
        )

    def _find_command(
        self,
        command: RevisePlan,
    ) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT type, request_hash, state, result_json, error_json
            FROM command_log
            WHERE command_id = ?
            """,
            (str(command.command_id),),
        ).fetchone()

    def _validate_stored_result(
        self,
        command: RevisePlan,
        stored: CommandResult,
    ) -> None:
        if (
            stored.command_id != command.command_id
            or stored.status != CommandStatus.ACCEPTED
            or len(stored.event_ids) != 1
        ):
            raise RuntimeError(
                f"stored CommandResult for {command.command_id} is not "
                "bound to the committed command"
            )

        event_id = stored.event_ids[0]
        event = self.connection.execute(
            """
            SELECT
                event.aggregate_type,
                event.aggregate_id,
                event.aggregate_version,
                event.type,
                event.causation_id,
                outbox.event_id AS outbox_event_id
            FROM events AS event
            LEFT JOIN outbox_events AS outbox
                ON outbox.event_id = event.id
            WHERE event.id = ?
            """,
            (event_id,),
        ).fetchone()
        revision_key = f"plan:{command.plan_id}"
        expected_revisions = (
            {revision_key: int(event["aggregate_version"])}
            if event is not None
            else None
        )
        plan_exists = (
            event is not None
            and self.connection.execute(
                """
                SELECT 1
                FROM plans
                WHERE id = ? AND revision = ?
                """,
                (
                    str(command.plan_id),
                    int(event["aggregate_version"]),
                ),
            ).fetchone()
            is not None
        )
        if (
            event is None
            or event["aggregate_type"] != "plan"
            or event["aggregate_id"] != str(command.plan_id)
            or event["type"] != "plan.revised"
            or event["causation_id"] != str(command.command_id)
            or event["outbox_event_id"] != event_id
            or dict(stored.affected_revisions) != expected_revisions
            or not plan_exists
        ):
            raise RuntimeError(
                f"stored CommandResult for {command.command_id} is not "
                "bound to its domain revision, Event, and outbox row"
            )

    def _validate_stored_rejection(
        self,
        command: RevisePlan,
        stored: StructuredError,
    ) -> None:
        actual_revision = stored.details.get("actual_revision")
        if (
            isinstance(actual_revision, bool)
            or (
                actual_revision is not None
                and (
                    not isinstance(actual_revision, int)
                    or actual_revision < 1
                )
            )
        ):
            raise RuntimeError(
                f"stored Command rejection for {command.command_id} is not "
                "bound to the rejected command"
            )
        expected = self._revision_conflict(command, actual_revision)
        revision_exists = (
            actual_revision is None
            or self.connection.execute(
                """
                SELECT 1
                FROM plans
                WHERE id = ? AND revision = ?
                """,
                (str(command.plan_id), actual_revision),
            ).fetchone()
            is not None
        )
        if (
            stored.model_dump(mode="json")
            != expected.model_dump(mode="json")
            or not revision_exists
        ):
            raise RuntimeError(
                f"stored Command rejection for {command.command_id} is not "
                "bound to the rejected command"
            )

    def _replay(
        self,
        row: sqlite3.Row,
        command: RevisePlan,
        request_hash: str,
    ) -> CommandResult:
        if row["type"] != command.type or row["request_hash"] != request_hash:
            raise CommandExecutionError(
                StructuredError(
                    code=ErrorCode.COMMAND_REPLAY_CONFLICT,
                    category=ErrorCategory.CONFLICT,
                    message=(
                        f"command_id {command.command_id} was already used "
                        "for different content"
                    ),
                    retryable=False,
                    details={"command_id": str(command.command_id)},
                    data_safe=True,
                    suggested_actions=(
                        "Use a new command_id for changed content.",
                    ),
                )
            )
        if row["state"] == "accepted" and row["result_json"] is not None:
            stored = CommandResult.model_validate(
                json.loads(str(row["result_json"]))
            )
            self._validate_stored_result(command, stored)
            return stored.model_copy(
                update={"status": CommandStatus.REPLAYED}
            )
        if row["state"] == "rejected" and row["error_json"] is not None:
            error = StructuredError.model_validate(
                json.loads(str(row["error_json"]))
            )
            self._validate_stored_rejection(command, error)
            raise CommandExecutionError(error, replayed=True)
        raise RuntimeError(
            f"command_log row for {command.command_id} is incomplete"
        )

    @staticmethod
    def _request_hash(command: RevisePlan) -> str:
        serialized = _json(command.model_dump(mode="json")).encode("utf-8")
        return f"sha256:{hashlib.sha256(serialized).hexdigest()}"

    @staticmethod
    def _revision_conflict(
        command: RevisePlan,
        actual_revision: int | None,
    ) -> StructuredError:
        return StructuredError(
            code=ErrorCode.REVISION_CONFLICT,
            category=ErrorCategory.CONFLICT,
            message=(
                f"Plan {command.plan_id} revision conflict: expected "
                f"{command.expected_revision}, actual {actual_revision}"
            ),
            retryable=True,
            details={
                "aggregate_type": "plan",
                "aggregate_id": str(command.plan_id),
                "expected_revision": command.expected_revision,
                "actual_revision": actual_revision,
            },
            data_safe=True,
            suggested_actions=(
                "Reload the Plan and retry with its current revision.",
            ),
        )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._require_idle()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _require_idle(self) -> None:
        if self.connection.in_transaction:
            raise RuntimeError(
                "Command transaction service requires an idle SQLite connection"
            )
