"""Read-only canonical bootstrap projection for the D3 runtime."""

from __future__ import annotations

import json
import base64
import binascii
import hashlib
import hmac
import sqlite3
from pathlib import Path
from typing import Any

from nana_sidecar.storage import connect_database_readonly


MAX_BOOTSTRAP_BYTES = 2 * 1024 * 1024
_BOOTSTRAP_KNOWN_EVENT_KEYS = (
    "workspace:workspace.created",
    "project:project.created", "project:project.status_changed",
    "inquiry:inquiry.created", "inquiry:inquiry.status_changed",
    "plan:plan.proposed", "plan:plan.revised", "plan:plan.status_changed",
    "resource:resource.registered", "locator:locator.created", "claim:claim.created",
    "evidence:evidence.attached", "hypothesis:hypothesis.created", "finding:finding.drafted",
    "run:run.created", "run:run.started", "run:run.heartbeat", "run:run.paused",
    "run:run.cancelled", "run:run.timed_out", "run:run.failed", "run:run.succeeded",
    "run:run.budget_exceeded", "run:run.orphaned",
    "action:action.proposed", "action:action.authorized", "action:action.started",
    "action:action.output", "action:action.completed", "action:action.cancelled",
    "action:action.effect_unknown",
    "approval:approval.requested", "approval:approval.decided", "approval:approval.expired",
    "budget:budget.updated", "budget:budget.threshold_reached",
    "relation:relation.created",
    "artifact:artifact.staged", "artifact:artifact.committed", "artifact:artifact.reconciled",
)


class SnapshotTooLargeError(RuntimeError):
    """The bounded bootstrap response needs a section/page request."""

    def __init__(self, message: str, *, sections: list[str], page_tokens: dict[str, str]) -> None:
        super().__init__(message)
        self.sections = sections
        self.page_tokens = page_tokens


class PageTooLargeError(RuntimeError):
    """One signed section page still exceeds the response ceiling."""

    def __init__(self, section: str) -> None:
        super().__init__("E_SECTION_PAGE_TOO_LARGE")
        self.section = section


def _json(value: str | None, fallback: object) -> object:
    return fallback if value is None else json.loads(value)


def _rows(connection: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(sql, params).fetchall()]


class BootstrapReadModel:
    """Project display-safe canonical facts from one SQLite read snapshot."""

    def __init__(self, database_path: str | Path, *, token_secret: str | bytes = "d3-local-page-token") -> None:
        self.database_path = Path(database_path)
        self._token_secret = token_secret.encode("utf-8") if isinstance(token_secret, str) else token_secret

    def snapshot(self) -> dict[str, object]:
        connection = connect_database_readonly(self.database_path)
        try:
            connection.execute("BEGIN")
            high_water = int(
                connection.execute(
                    "SELECT COALESCE(MAX(event.id), 0) AS id "
                    "FROM events AS event "
                    "INNER JOIN outbox_events AS outbox ON outbox.event_id = event.id"
                ).fetchone()["id"]
            )
            projection = {
                "high_water_event_id": high_water,
                "projection_status": self._projection_status(connection, high_water),
                "workspace": self._workspace(connection),
                "projects": _rows(
                    connection,
                    "SELECT id, workspace_id, title, status, data_class, revision, created_at "
                    "FROM projects ORDER BY id",
                ),
                "inquiries": _rows(
                    connection,
                    "SELECT id, project_id, question, acceptance, status, revision, created_at "
                    "FROM inquiries ORDER BY id",
                ),
                "plans": self._plans(connection),
                "resources": _rows(
                    connection,
                    "SELECT id, project_id, kind, logical_ref, content_hash, media_type, "
                    "status, revision FROM resources ORDER BY id",
                ),
                "locators": _rows(
                    connection,
                    "SELECT id, resource_id, locator_type, quote_hash, status, revision "
                    "FROM locators ORDER BY id",
                ),
                "claims": _rows(
                    connection,
                    "SELECT id, inquiry_id, statement, status, revision FROM claims ORDER BY id",
                ),
                "evidence": _rows(
                    connection,
                    "SELECT id, inquiry_id, locator_id, direction, excerpt_hash, status "
                    "FROM evidence ORDER BY id",
                ),
                "hypotheses": _rows(
                    connection,
                    "SELECT id, inquiry_id, statement, falsification_criteria, status "
                    "FROM hypotheses ORDER BY id",
                ),
                "runs": self._runs(connection),
                "actions": _rows(
                    connection,
                    "SELECT id, run_id, plan_step_id, capability_id, state, started_at, finished_at "
                    "FROM actions ORDER BY id",
                ),
                "receipts": self._receipts(connection),
                "approvals": self._approvals(connection),
                "exports": self._exports(connection),
                "artifacts": _rows(
                    connection,
                    "SELECT id, media_type, blob_hash, size, state, producer_run_id, created_at "
                    "FROM artifacts ORDER BY id",
                ),
                "findings": self._findings(connection),
                "needs_you": _rows(
                    connection,
                    "SELECT actions.id AS action_id, actions.run_id, actions.state, "
                    "approvals.id AS approval_id, approvals.subject_hash, approvals.expires_at "
                    "FROM actions LEFT JOIN approvals ON approvals.subject_type = 'action' "
                    "AND approvals.subject_id = actions.id AND approvals.decision = 'requested' "
                    "WHERE actions.state = 'waiting_approval' ORDER BY actions.id",
                ),
                "activity": self._activity(connection, high_water),
                "aggregate_versions": self._aggregate_versions(connection, high_water),
                "run_sequences": self._run_sequences(connection, high_water),
            }
            encoded = json.dumps(
                projection,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(encoded) > MAX_BOOTSTRAP_BYTES:
                sections = ["research", "execution", "artifacts", "findings", "activity"]
                raise SnapshotTooLargeError("E_SNAPSHOT_TOO_LARGE", sections=sections, page_tokens={
                    section: self._encode_token(high_water, section, 0, self._watermark_payload(projection))
                    for section in sections
                })
            connection.commit()
            return projection
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def page(self, *, section: str, token: str, limit: int = 100) -> dict[str, object]:
        if section not in {"research", "execution", "artifacts", "findings", "activity"}:
            raise ValueError("E_PAGE_SECTION")
        decoded = self._decode_token(token)
        if decoded["section"] != section:
            raise ValueError("E_PAGE_TOKEN_SECTION")
        offset = int(decoded["offset"])
        limit = max(1, min(int(limit), 200))
        connection = connect_database_readonly(self.database_path)
        try:
            connection.execute("BEGIN")
            rows = self._section_rows(connection, section, int(decoded["high_water"]), offset, limit)
            next_token = None
            if len(rows) == limit:
                next_token = self._encode_token(int(decoded["high_water"]), section, offset + len(rows), decoded["watermarks"])
            connection.commit()
            response = {
                "section": section,
                "high_water_event_id": int(decoded["high_water"]),
                "aggregate_versions": decoded["watermarks"]["aggregate_versions"],
                "run_sequences": decoded["watermarks"]["run_sequences"],
                "rows": rows,
                "next_page_token": next_token,
            }
            if len(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) > MAX_BOOTSTRAP_BYTES:
                raise PageTooLargeError(section)
            return response
        finally:
            connection.close()

    @staticmethod
    def _watermark_payload(projection: dict[str, object]) -> dict[str, object]:
        return {"aggregate_versions": projection["aggregate_versions"], "run_sequences": projection["run_sequences"]}

    @staticmethod
    def _projection_status(connection: sqlite3.Connection, high_water: int) -> str:
        placeholders = ",".join("?" for _ in _BOOTSTRAP_KNOWN_EVENT_KEYS)
        unknown = connection.execute(
            "SELECT 1 FROM events AS event INNER JOIN outbox_events AS outbox "
            "ON outbox.event_id = event.id "
            "WHERE event.id <= ? AND event.aggregate_type || ':' || event.type NOT IN (" + placeholders + ") LIMIT 1",
            (high_water, *_BOOTSTRAP_KNOWN_EVENT_KEYS),
        ).fetchone()
        return "degraded" if unknown is not None else "ready"

    def _encode_token(self, high_water: int, section: str, offset: int, watermarks: dict[str, object]) -> str:
        payload = {"high_water": high_water, "section": section, "offset": offset, "watermarks": watermarks}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self._token_secret, raw, hashlib.sha256).digest()
        encoded_payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{encoded_payload}.{encoded_signature}"

    def _decode_token(self, token: str) -> dict[str, object]:
        try:
            if not isinstance(token, str):
                raise ValueError
            encoded_payload, separator, encoded_signature = token.partition(".")
            if not separator or not encoded_payload or not encoded_signature or "." in encoded_signature:
                raise ValueError
            alphabet = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
            if not set(encoded_payload) <= alphabet or not set(encoded_signature) <= alphabet:
                raise ValueError
            raw = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
            signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
            if (
                base64.urlsafe_b64encode(raw).decode().rstrip("=") != encoded_payload
                or base64.urlsafe_b64encode(signature).decode().rstrip("=") != encoded_signature
            ):
                raise ValueError
            if not hmac.compare_digest(signature, hmac.new(self._token_secret, raw, hashlib.sha256).digest()):
                raise ValueError
            decoded = json.loads(raw)
            if (
                not isinstance(decoded, dict)
                or not isinstance(decoded.get("watermarks"), dict)
                or not isinstance(decoded.get("section"), str)
                or type(decoded.get("high_water")) is not int
                or type(decoded.get("offset")) is not int
                or decoded["high_water"] < 0
                or decoded["offset"] < 0
                or decoded["offset"] > 10_000_000
            ):
                raise ValueError
            return decoded
        except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error) as exc:
            raise ValueError("E_PAGE_TOKEN") from exc

    @staticmethod
    def _section_rows(connection: sqlite3.Connection, section: str, high_water: int, offset: int, limit: int) -> list[dict[str, object]]:
        predicates = {
            "activity": "1 = 1",
            "research": "aggregate_type IN ('workspace', 'project', 'inquiry', 'plan', 'resource', 'locator', 'claim', 'evidence')",
            "execution": "aggregate_type IN ('run', 'action', 'budget', 'policy_grant', 'approval')",
            "artifacts": "aggregate_type = 'artifact'",
            "findings": "aggregate_type IN ('finding', 'hypothesis', 'relation')",
        }
        return _rows(
            connection,
            "SELECT event.id, event.aggregate_type, event.aggregate_id, event.aggregate_version, "
            "event.run_id, event.run_seq, event.action_id, event.type, event.occurred_at "
            "FROM events AS event INNER JOIN outbox_events AS outbox ON outbox.event_id = event.id "
            "WHERE event.id <= ? AND " + predicates[section].replace("aggregate_type", "event.aggregate_type")
            + " ORDER BY event.id LIMIT ? OFFSET ?",
            (high_water, limit, offset),
        )

    @staticmethod
    def _workspace(connection: sqlite3.Connection) -> dict[str, object] | None:
        row = connection.execute(
            "SELECT id, schema_version, status, revision FROM workspaces ORDER BY id LIMIT 1"
        ).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _plans(connection: sqlite3.Connection) -> list[dict[str, object]]:
        result = []
        for row in connection.execute(
            "SELECT id, inquiry_id, revision, status, steps_json, created_at "
            "FROM plans ORDER BY id, revision"
        ):
            steps = _json(str(row["steps_json"]), [])
            safe_steps = [
                {
                    "id": step.get("id"),
                    "title": step.get("title"),
                    "approval_required": bool(step.get("approval_required", False)),
                }
                for step in steps
                if isinstance(step, dict)
            ]
            result.append(
                {
                    "id": row["id"],
                    "inquiry_id": row["inquiry_id"],
                    "revision": row["revision"],
                    "status": row["status"],
                    "steps": safe_steps,
                    "created_at": row["created_at"],
                }
            )
        return result

    @staticmethod
    def _runs(connection: sqlite3.Connection) -> list[dict[str, object]]:
        return _rows(
            connection,
            "SELECT id, project_id, inquiry_id, state, retry_of_run_id, created_at, finished_at "
            "FROM runs ORDER BY id",
        )

    @staticmethod
    def _receipts(connection: sqlite3.Connection) -> list[dict[str, object]]:
        result = []
        for row in connection.execute(
            "SELECT id, action_id, result, effect_violation, resource_usage_json, created_at "
            "FROM action_receipts ORDER BY id"
        ):
            usage = _json(str(row["resource_usage_json"]), {})
            receipt_result = str(row["result"])
            billing_basis = (
                "conservative_uncertain_effect"
                if receipt_result in {"effect_unknown", "timed_out"}
                else "not_charged_pre_spawn"
                if receipt_result == "cancelled"
                else "measured_observed_effect"
            )
            result.append(
                {
                    "id": row["id"],
                    "action_id": row["action_id"],
                    "result": receipt_result,
                    "effect_violation": bool(row["effect_violation"]),
                    "billing_basis": billing_basis,
                    "resource_usage": {
                        key: usage.get(key, 0)
                        for key in (
                            "wall_clock_ms",
                            "output_bytes",
                            "artifact_bytes",
                            "model_tokens",
                            "cost_micros",
                        )
                        if isinstance(usage, dict)
                    },
                    "created_at": row["created_at"],
                }
            )
        return result

    @staticmethod
    def _approvals(connection: sqlite3.Connection) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in connection.execute(
            "SELECT approvals.id, approvals.subject_type, approvals.subject_id, "
            "approvals.subject_hash, approvals.capability_json, approvals.risk_tier, "
            "approvals.expires_at, approvals.decision, approvals.decided_at, "
            "COALESCE(MAX(events.aggregate_version), 0) AS revision "
            "FROM approvals LEFT JOIN events ON events.aggregate_type = 'approval' "
            "AND events.aggregate_id = approvals.id "
            "GROUP BY approvals.id ORDER BY approvals.id"
        ):
            capability = _json(str(row["capability_json"]), {})
            result.append(
                {
                    "id": row["id"],
                    "subject_type": row["subject_type"],
                    "subject_id": row["subject_id"],
                    "subject_hash": row["subject_hash"],
                    "capability_id": (
                        capability.get("id") if isinstance(capability, dict) else None
                    ),
                    "risk_tier": row["risk_tier"],
                    "expires_at": row["expires_at"],
                    "decision": row["decision"],
                    "decided_at": row["decided_at"],
                    "revision": int(row["revision"]),
                    "consumed": connection.execute(
                        "SELECT 1 FROM approval_consumptions WHERE approval_id = ?",
                        (row["id"],),
                    ).fetchone() is not None,
                }
            )
        return result

    @staticmethod
    def _exports(connection: sqlite3.Connection) -> list[dict[str, object]]:
        return _rows(
            connection,
            "SELECT actions.id AS action_id, actions.run_id, actions.state, "
            "actions.args_artifact_id, approvals.id AS approval_id, "
            "approvals.decision AS approval_decision, "
            "CASE WHEN external_write_fences.action_id IS NULL THEN 0 ELSE 1 END AS write_fenced "
            "FROM actions LEFT JOIN approvals ON approvals.subject_type = 'action' "
            "AND approvals.subject_id = actions.id "
            "LEFT JOIN external_write_fences ON external_write_fences.action_id = actions.id "
            "WHERE actions.capability_id = 'export.draft_external' ORDER BY actions.id",
        )

    @staticmethod
    def _findings(connection: sqlite3.Connection) -> list[dict[str, object]]:
        result = []
        for row in connection.execute(
            "SELECT id, inquiry_id, statement, status, confidence_basis, evidence_ids_json, "
            "producer_run_id, revision FROM findings ORDER BY id"
        ):
            result.append(
                {
                    "id": row["id"],
                    "inquiry_id": row["inquiry_id"],
                    "statement": row["statement"],
                    "status": row["status"],
                    "confidence_basis": row["confidence_basis"],
                    "evidence_ids": _json(str(row["evidence_ids_json"]), []),
                    "producer_run_id": row["producer_run_id"],
                    "revision": row["revision"],
                }
            )
        return result

    @staticmethod
    def _activity(connection: sqlite3.Connection, high_water: int) -> list[dict[str, object]]:
        return _rows(
            connection,
            "SELECT event.id, event.aggregate_type, event.aggregate_id, event.aggregate_version, "
            "event.run_id, event.run_seq, event.action_id, event.type, event.occurred_at "
            "FROM events AS event INNER JOIN outbox_events AS outbox ON outbox.event_id = event.id "
            "WHERE event.id <= ? ORDER BY event.id DESC LIMIT 200",
            (high_water,),
        )[::-1]

    @staticmethod
    def _aggregate_versions(connection: sqlite3.Connection, high_water: int) -> dict[str, int]:
        return {
            f"{row['aggregate_type']}:{row['aggregate_id']}": int(row["aggregate_version"])
            for row in connection.execute(
                "SELECT event.aggregate_type, event.aggregate_id, MAX(event.aggregate_version) AS aggregate_version "
                "FROM events AS event INNER JOIN outbox_events AS outbox ON outbox.event_id = event.id "
                "WHERE event.id <= ? GROUP BY event.aggregate_type, event.aggregate_id",
                (high_water,),
            )
        }

    @staticmethod
    def _run_sequences(connection: sqlite3.Connection, high_water: int) -> dict[str, int]:
        return {
            str(row["run_id"]): int(row["run_seq"])
            for row in connection.execute(
                "SELECT event.run_id, MAX(event.run_seq) AS run_seq "
                "FROM events AS event INNER JOIN outbox_events AS outbox ON outbox.event_id = event.id "
                "WHERE event.id <= ? AND event.run_id IS NOT NULL GROUP BY event.run_id",
                (high_water,),
            )
        }
