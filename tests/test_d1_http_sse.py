"""D1-06 gate for authenticated, resumable HTTP SSE delivery."""

from __future__ import annotations

import asyncio
import json
import math
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from nana_sidecar.runtime_app import create_runtime_app
from nana_sidecar.sse import LocalSession, SQLiteEventStream
from nana_sidecar.storage import connect_database, initialize_database


NOW = "2026-07-30T00:00:00Z"
ORIGIN = "http://127.0.0.1:43123"
TOKEN = "d1-session-" + ("a" * 43)
PLAN_ID = UUID("00000000-0000-0000-0000-000000000601")


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _frame_id(frame: str) -> int:
    for line in frame.splitlines():
        if line.startswith("id: "):
            return int(line.removeprefix("id: "))
    raise AssertionError(f"SSE frame has no id: {frame!r}")


class OpenASGIStream:
    """Drive one streaming ASGI request without buffering the response."""

    def __init__(
        self,
        app: Any,
        *,
        last_event_id: int | None = None,
        raw_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        self.app = app
        self.last_event_id = last_event_id
        self.raw_headers = raw_headers
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self.response_start: dict[str, Any] | None = None

    async def open(self) -> None:
        if self.raw_headers is None:
            headers = [
                (b"host", b"127.0.0.1:43123"),
                (b"origin", ORIGIN.encode("ascii")),
                (b"authorization", f"Bearer {TOKEN}".encode("ascii")),
            ]
            if self.last_event_id is not None:
                headers.append(
                    (
                        b"last-event-id",
                        str(self.last_event_id).encode("ascii"),
                    )
                )
        else:
            headers = list(self.raw_headers)
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/events",
            "raw_path": b"/api/v1/events",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 43123),
            "root_path": "",
        }
        await self._receive_queue.put(
            {"type": "http.request", "body": b"", "more_body": False}
        )

        async def receive() -> dict[str, Any]:
            return await self._receive_queue.get()

        async def send(message: dict[str, Any]) -> None:
            await self._send_queue.put(message)

        self._task = asyncio.create_task(self.app(scope, receive, send))
        self.response_start = await asyncio.wait_for(
            self._send_queue.get(),
            timeout=1,
        )
        if self.response_start["type"] != "http.response.start":
            raise AssertionError(self.response_start)

    async def next_frame(self) -> str:
        while True:
            message = await asyncio.wait_for(
                self._send_queue.get(),
                timeout=1,
            )
            if message["type"] != "http.response.body":
                continue
            body = bytes(message.get("body", b""))
            if body:
                return body.decode("utf-8")
            if not message.get("more_body", False):
                raise EOFError("SSE response ended")

    async def close(self) -> None:
        if self._task is None:
            return
        await self._receive_queue.put({"type": "http.disconnect"})
        try:
            await asyncio.wait_for(self._task, timeout=1)
        except asyncio.TimeoutError:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)


class CountingEventStream(SQLiteEventStream):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.batch_sizes: list[int] = []

    def _read_batch(self, connection: Any, after_id: int) -> tuple[Any, ...]:
        batch = super()._read_batch(connection, after_id)
        self.batch_sizes.append(len(batch))
        return batch


class TransitionEventStream(SQLiteEventStream):
    def __init__(
        self,
        *args: Any,
        on_first_empty: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.on_first_empty = on_first_empty
        self.fired = False

    def _read_batch(self, connection: Any, after_id: int) -> tuple[Any, ...]:
        batch = super()._read_batch(connection, after_id)
        if not batch and not self.fired:
            self.fired = True
            self.on_first_empty()
        return batch


class D1HttpSSETests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "nana.db"
        self.connection = initialize_database(self.database_path)
        self.session = LocalSession(token=TOKEN, origin=ORIGIN)
        self.stream = SQLiteEventStream(
            self.database_path,
            poll_interval=0.01,
            batch_size=2,
        )
        self.app = create_runtime_app(
            event_stream=self.stream,
            local_session=self.session,
        )

    async def asyncTearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _insert_event(self, revision: int) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES ('plan', ?, ?, ?, 'plan.revised', ?, ?)
            """,
            (
                str(PLAN_ID),
                revision,
                _json({"kind": "user", "id": "owner"}),
                _json(
                    {
                        "plan_id": str(PLAN_ID),
                        "revision": revision,
                    }
                ),
                NOW,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (event_id,),
        )
        self.connection.commit()
        return event_id

    async def _open_stream(
        self,
        *,
        last_event_id: int | None = None,
    ) -> OpenASGIStream:
        opened = OpenASGIStream(
            self.app,
            last_event_id=last_event_id,
        )
        await opened.open()
        self.assertEqual(opened.response_start["status"], 200)
        headers = dict(opened.response_start["headers"])
        self.assertTrue(
            headers[b"content-type"].startswith(b"text/event-stream")
        )
        self.assertEqual(
            headers[b"cache-control"],
            b"no-cache, no-transform",
        )
        self.assertEqual(headers[b"x-accel-buffering"], b"no")
        return opened

    async def test_last_event_id_replays_in_global_id_order(self) -> None:
        event_ids = [self._insert_event(revision) for revision in range(1, 4)]

        opened = await self._open_stream(last_event_id=event_ids[0])
        try:
            frames = [await opened.next_frame() for _ in range(2)]
        finally:
            await opened.close()

        self.assertEqual(
            [_frame_id(frame) for frame in frames],
            event_ids[1:],
        )
        payloads = [
            json.loads(
                next(
                    line.removeprefix("data: ")
                    for line in frame.splitlines()
                    if line.startswith("data: ")
                )
            )
            for frame in frames
        ]
        self.assertEqual(
            [payload["id"] for payload in payloads],
            event_ids[1:],
        )

    async def test_catch_up_to_live_transition_has_no_gap(self) -> None:
        first = self._insert_event(1)
        inserted_live: list[int] = []
        stream = TransitionEventStream(
            self.database_path,
            poll_interval=0.01,
            batch_size=2,
            on_first_empty=lambda: inserted_live.append(
                self._insert_event(2)
            ),
        )
        iterator = stream.iter_sse(after_id=0)
        try:
            self.assertEqual(_frame_id(await anext(iterator)), first)
            self.assertEqual(
                _frame_id(
                    await asyncio.wait_for(anext(iterator), timeout=1)
                ),
                inserted_live[0],
            )
            self.assertTrue(stream.fired)
        finally:
            await iterator.aclose()

    async def test_uncommitted_event_and_outbox_are_invisible(self) -> None:
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES ('plan', ?, 1, ?, 'plan.revised', ?, ?)
            """,
            (
                str(PLAN_ID),
                _json({"kind": "user", "id": "owner"}),
                _json({"plan_id": str(PLAN_ID), "revision": 1}),
                NOW,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (event_id,),
        )
        iterator = self.stream.iter_sse(after_id=0)
        pending = asyncio.create_task(anext(iterator))
        try:
            await asyncio.sleep(0.03)
            self.assertFalse(pending.done())
            self.connection.commit()
            self.assertEqual(
                _frame_id(await asyncio.wait_for(pending, timeout=1)),
                event_id,
            )
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await iterator.aclose()

    async def test_disconnect_reconnect_replays_every_missing_event(self) -> None:
        event_ids = [self._insert_event(revision) for revision in range(1, 3)]

        first_connection = await self._open_stream(last_event_id=0)
        first_frame = await first_connection.next_frame()
        await first_connection.close()
        self.assertEqual(_frame_id(first_frame), event_ids[0])

        event_ids.append(self._insert_event(3))
        reconnected = await self._open_stream(last_event_id=event_ids[0])
        try:
            replayed = [await reconnected.next_frame() for _ in range(2)]
        finally:
            await reconnected.close()

        self.assertEqual(
            [_frame_id(frame) for frame in replayed],
            event_ids[1:],
        )

    async def test_slow_client_only_prefetches_one_bounded_batch(self) -> None:
        event_ids = [self._insert_event(revision) for revision in range(1, 6)]
        stream = CountingEventStream(
            self.database_path,
            poll_interval=0.01,
            batch_size=2,
        )
        iterator = stream.iter_sse(after_id=0)
        try:
            first = await anext(iterator)
            await asyncio.sleep(0.03)
            self.assertEqual(_frame_id(first), event_ids[0])
            self.assertEqual(stream.batch_sizes, [2])

            second = await anext(iterator)
            self.assertEqual(_frame_id(second), event_ids[1])
            self.assertEqual(stream.batch_sizes, [2])

            third = await anext(iterator)
            self.assertEqual(_frame_id(third), event_ids[2])
            self.assertEqual(stream.batch_sizes, [2, 2])
        finally:
            await iterator.aclose()

    async def test_batch_size_has_a_hard_memory_bound(self) -> None:
        for invalid in (0, 1025, True, 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "batch_size"):
                    SQLiteEventStream(
                        self.database_path,
                        batch_size=invalid,
                    )

    async def test_poll_interval_must_be_finite_positive_number(self) -> None:
        for invalid in (0, -1, math.nan, math.inf, -math.inf, True):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "poll_interval"):
                    SQLiteEventStream(
                        self.database_path,
                        poll_interval=invalid,
                    )

    async def test_http_disconnect_closes_stream_database_connection(
        self,
    ) -> None:
        event_id = self._insert_event(1)
        real_connection = connect_database(self.database_path)
        tracked_connection = MagicMock(wraps=real_connection)
        with patch(
            "nana_sidecar.sse.connect_database",
            return_value=tracked_connection,
        ):
            opened = await self._open_stream(last_event_id=0)
            self.assertEqual(_frame_id(await opened.next_frame()), event_id)
            await opened.close()

        tracked_connection.close.assert_called_once_with()

    async def test_every_connection_requires_same_session_and_origin(
        self,
    ) -> None:
        event_id = self._insert_event(1)
        async with AsyncClient(
            transport=ASGITransport(app=self.app),
            base_url=ORIGIN,
        ) as client:
            missing_session = await client.get(
                "/api/v1/events",
                headers={"Origin": ORIGIN},
            )
            wrong_session = await client.get(
                "/api/v1/events",
                headers={
                    "Origin": ORIGIN,
                    "Authorization": "Bearer wrong",
                },
            )
            missing_origin = await client.get(
                "/api/v1/events",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            wrong_origin = await client.get(
                "/api/v1/events",
                headers={
                    "Origin": "http://evil.invalid",
                    "Authorization": f"Bearer {TOKEN}",
                },
            )
            anonymous_api = await client.get("/api/v1/contracts")
            authenticated_api = await client.get(
                "/api/v1/contracts",
                headers={
                    "Origin": ORIGIN,
                    "Authorization": f"Bearer {TOKEN}",
                },
            )

        self.assertEqual(missing_session.status_code, 401)
        self.assertEqual(wrong_session.status_code, 401)
        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(wrong_origin.status_code, 403)
        self.assertEqual(anonymous_api.status_code, 401)
        self.assertEqual(authenticated_api.status_code, 200)

        accepted = await self._open_stream(last_event_id=0)
        try:
            self.assertEqual(_frame_id(await accepted.next_frame()), event_id)
        finally:
            await accepted.close()

    async def test_future_routes_default_to_session_and_slash_cannot_bypass(
        self,
    ) -> None:
        @self.app.post("/api/v1/future-mutation")
        async def future_mutation() -> dict[str, bool]:
            return {"accepted": True}

        session_headers = {
            "Origin": ORIGIN,
            "Authorization": f"Bearer {TOKEN}",
        }
        async with AsyncClient(
            transport=ASGITransport(app=self.app),
            base_url=ORIGIN,
        ) as client:
            health = await client.get("/healthz")
            handshake = await client.get("/api/v1/handshake")
            openapi = await client.get("/openapi.json")
            anonymous_mutation = await client.post(
                "/api/v1/future-mutation",
            )
            anonymous_mutation_slash = await client.post(
                "/api/v1/future-mutation/",
                follow_redirects=False,
            )
            anonymous_contracts_slash = await client.get(
                "/api/v1/contracts/",
                follow_redirects=False,
            )
            anonymous_unknown = await client.get("/api/v1/future-unknown")
            authenticated_mutation = await client.post(
                "/api/v1/future-mutation",
                headers=session_headers,
            )
            authenticated_contracts_slash = await client.get(
                "/api/v1/contracts/",
                headers=session_headers,
                follow_redirects=True,
            )
            authenticated_unknown = await client.get(
                "/api/v1/future-unknown",
                headers=session_headers,
            )

        self.assertEqual(health.status_code, 200)
        self.assertEqual(handshake.status_code, 200)
        self.assertEqual(openapi.status_code, 200)
        self.assertEqual(anonymous_mutation.status_code, 401)
        self.assertEqual(anonymous_mutation_slash.status_code, 401)
        self.assertEqual(anonymous_contracts_slash.status_code, 401)
        self.assertEqual(anonymous_unknown.status_code, 401)
        self.assertEqual(authenticated_mutation.status_code, 200)
        self.assertEqual(authenticated_mutation.json(), {"accepted": True})
        self.assertEqual(authenticated_contracts_slash.status_code, 200)
        self.assertEqual(authenticated_unknown.status_code, 404)

    async def test_ambiguous_security_and_cursor_headers_are_rejected(
        self,
    ) -> None:
        self._insert_event(1)
        base_headers = [
            (b"host", b"127.0.0.1:43123"),
            (b"origin", ORIGIN.encode("ascii")),
            (b"authorization", f"Bearer {TOKEN}".encode("ascii")),
        ]
        cases = (
            (
                base_headers
                + [(b"authorization", b"Bearer attacker-controlled")],
                401,
            ),
            (
                base_headers
                + [(b"origin", b"http://attacker.invalid")],
                403,
            ),
            (
                base_headers
                + [(b"last-event-id", b"0"), (b"last-event-id", b"1")],
                400,
            ),
            (
                [
                    (b"host", b"127.0.0.1:43123"),
                    (b"origin", ORIGIN.encode("ascii")),
                    (b"authorization", b"Bearer \xff"),
                ],
                401,
            ),
        )

        for raw_headers, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                opened = OpenASGIStream(
                    self.app,
                    raw_headers=raw_headers,
                )
                await opened.open()
                try:
                    self.assertEqual(
                        opened.response_start["status"],
                        expected_status,
                    )
                finally:
                    await opened.close()

    async def test_invalid_last_event_id_is_rejected_over_http(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=self.app),
            base_url=ORIGIN,
        ) as client:
            for invalid in (
                "",
                "-1",
                "1.5",
                "9223372036854775808",
                "9" * 5_000,
            ):
                with self.subTest(invalid=invalid):
                    response = await client.get(
                        "/api/v1/events",
                        headers={
                            "Origin": ORIGIN,
                            "Authorization": f"Bearer {TOKEN}",
                            "Last-Event-ID": invalid,
                        },
                    )
                    self.assertEqual(response.status_code, 400)

    async def test_session_origin_must_be_explicit_loopback_origin(
        self,
    ) -> None:
        for invalid in (
            "http://evil.invalid:43123",
            "http://127.0.0.1:43123/path",
            "http://127.0.0.1",
            "http://user@127.0.0.1:43123",
            "not-an-origin",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "loopback"):
                    LocalSession(token=TOKEN, origin=invalid)

        with self.assertRaisesRegex(ValueError, "ASCII"):
            LocalSession(token="密" * 32, origin=ORIGIN)

    async def test_stream_and_session_configuration_fail_closed_as_pair(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "configured together"):
            create_runtime_app(event_stream=self.stream)
        with self.assertRaisesRegex(ValueError, "configured together"):
            create_runtime_app(local_session=self.session)

        async with AsyncClient(
            transport=ASGITransport(app=self.app),
            base_url=ORIGIN,
        ) as client:
            schema = (await client.get("/openapi.json")).json()
        self.assertIn("/api/v1/events", schema["paths"])


if __name__ == "__main__":
    unittest.main()
