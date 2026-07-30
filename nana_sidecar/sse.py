"""Authenticated, resumable HTTP SSE projection of canonical Events."""

from __future__ import annotations

import asyncio
import hmac
import json
import math
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from starlette.datastructures import Headers

from nana_sidecar.contracts.domain import Event
from nana_sidecar.storage import connect_database


_MAX_SQLITE_INTEGER = (1 << 63) - 1
_MAX_SQLITE_INTEGER_TEXT = str(_MAX_SQLITE_INTEGER)
_MAX_BATCH_SIZE = 1024


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def parse_last_event_id(value: str | None) -> int:
    """Parse the numeric global Event cursor carried by HTTP SSE."""

    if value is None:
        return 0
    if not value.isascii() or not value.isdecimal():
        raise HTTPException(
            status_code=400,
            detail="Last-Event-ID must be a non-negative decimal integer",
        )
    if (
        len(value) > len(_MAX_SQLITE_INTEGER_TEXT)
        or (
            len(value) == len(_MAX_SQLITE_INTEGER_TEXT)
            and value > _MAX_SQLITE_INTEGER_TEXT
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Last-Event-ID exceeds the SQLite Event ID range",
        )
    cursor = int(value)
    return cursor


@dataclass(frozen=True, slots=True)
class LocalSession:
    """One in-memory local session shared by API and SSE requests."""

    token: str
    origin: str

    def __post_init__(self) -> None:
        try:
            encoded_token = self.token.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(
                "local session token must contain only ASCII characters"
            ) from exc
        if len(encoded_token) < 32:
            raise ValueError("local session token must be at least 32 bytes")
        valid_origin = False
        try:
            parsed = urlsplit(self.origin)
            host = parsed.hostname
            port = parsed.port
            valid_origin = (
                parsed.scheme in {"http", "https"}
                and host is not None
                and port is not None
                and parsed.username is None
                and parsed.password is None
                and parsed.path == ""
                and parsed.query == ""
                and parsed.fragment == ""
                and ip_address(host).is_loopback
            )
        except ValueError:
            valid_origin = False
        if not valid_origin:
            raise ValueError(
                "local session origin must be an explicit loopback HTTP(S) "
                "origin with a port"
            )

    def authorize(self, headers: Headers) -> None:
        authorization_values = headers.getlist("authorization")
        authorization = (
            authorization_values[0]
            if len(authorization_values) == 1
            else None
        )
        prefix = "Bearer "
        candidate = (
            authorization[len(prefix) :]
            if authorization is not None
            and authorization.startswith(prefix)
            else None
        )
        try:
            candidate_bytes = (
                candidate.encode("ascii")
                if candidate is not None
                else None
            )
        except UnicodeEncodeError:
            candidate_bytes = None
        if (
            candidate_bytes is None
            or not hmac.compare_digest(
                candidate_bytes,
                self.token.encode("ascii"),
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="valid local session required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        origin_values = headers.getlist("origin")
        if (
            len(origin_values) != 1
            or origin_values[0] != self.origin
        ):
            raise HTTPException(
                status_code=403,
                detail="request Origin is not the active local session Origin",
            )


class SQLiteEventStream:
    """Read committed outbox Events in bounded global-ID batches."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        poll_interval: float = 0.1,
        batch_size: int = 64,
    ) -> None:
        if (
            isinstance(poll_interval, bool)
            or not isinstance(poll_interval, (int, float))
            or not math.isfinite(poll_interval)
            or poll_interval <= 0
        ):
            raise ValueError(
                "poll_interval must be a finite positive number"
            )
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or not 1 <= batch_size <= _MAX_BATCH_SIZE
        ):
            raise ValueError(
                f"batch_size must be between 1 and {_MAX_BATCH_SIZE}"
            )
        self.database_path = Path(database_path)
        self.poll_interval = poll_interval
        self.batch_size = batch_size

    def _read_batch(
        self,
        connection: sqlite3.Connection,
        after_id: int,
    ) -> tuple[Event, ...]:
        rows = connection.execute(
            """
            SELECT
                event.id,
                event.aggregate_type,
                event.aggregate_id,
                event.aggregate_version,
                event.run_id,
                event.run_seq,
                event.action_id,
                event.actor_json,
                event.causation_id,
                event.correlation_id,
                event.type,
                event.payload_json,
                event.payload_artifact_id,
                event.occurred_at
            FROM events AS event
            INNER JOIN outbox_events AS outbox
                ON outbox.event_id = event.id
            WHERE event.id > ?
            ORDER BY event.id
            LIMIT ?
            """,
            (after_id, self.batch_size),
        ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> Event:
        return Event.model_validate(
            {
                "id": int(row["id"]),
                "aggregate_type": str(row["aggregate_type"]),
                "aggregate_id": str(row["aggregate_id"]),
                "aggregate_version": int(row["aggregate_version"]),
                "run_id": row["run_id"],
                "run_seq": row["run_seq"],
                "action_id": row["action_id"],
                "actor": json.loads(str(row["actor_json"])),
                "causation_id": row["causation_id"],
                "correlation_id": row["correlation_id"],
                "type": str(row["type"]),
                "payload": (
                    json.loads(str(row["payload_json"]))
                    if row["payload_json"] is not None
                    else None
                ),
                "payload_artifact_id": row["payload_artifact_id"],
                "occurred_at": str(row["occurred_at"]),
            }
        )

    @staticmethod
    def _format_event(event: Event) -> str:
        data = _json(event.model_dump(mode="json"))
        return (
            f"id: {event.id}\n"
            f"event: {event.type.value}\n"
            f"data: {data}\n\n"
        )

    async def iter_sse(self, *, after_id: int) -> AsyncIterator[str]:
        """Continuously catch up and then poll live without changing cursors."""

        connection = connect_database(self.database_path)
        cursor = after_id
        try:
            while True:
                batch = self._read_batch(connection, cursor)
                if batch:
                    for event in batch:
                        cursor = event.id
                        yield self._format_event(event)
                    continue
                await asyncio.sleep(self.poll_interval)
        finally:
            connection.close()
