"""D1-07 gate for 10,000 mixed Events over resumable HTTP SSE."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

from nana_sidecar.runtime_app import create_runtime_app
from nana_sidecar.sse import LocalSession, SQLiteEventStream
from nana_sidecar.storage import initialize_database


NOW = "2026-07-30T00:00:00Z"
ORIGIN = "http://127.0.0.1:43124"
TOKEN = "d1-gate-session-" + ("b" * 40)
WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000701")
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000702")
INQUIRY_ID = UUID("00000000-0000-0000-0000-000000000703")
PLAN_ID = UUID("00000000-0000-0000-0000-000000000704")
RUN_IDS = (
    UUID("00000000-0000-0000-0000-000000000705"),
    UUID("00000000-0000-0000-0000-000000000706"),
)
VERSIONS_PER_AGGREGATE = 2_500
EVENT_COUNT = 10_000


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _run_event(version: int) -> tuple[str, str]:
    if version == 1:
        return "run.created", "proposed"
    if version == 2:
        return "run.started", "running"
    if version == VERSIONS_PER_AGGREGATE:
        return "run.succeeded", "succeeded"
    return "run.heartbeat", "running"


def _event_rows() -> Iterator[tuple[object, ...]]:
    actor = _json({"kind": "system", "id": "d1-runtime-gate"})
    for version in range(1, VERSIONS_PER_AGGREGATE + 1):
        run_type, run_state = _run_event(version)
        for run_id in RUN_IDS:
            yield (
                "run",
                str(run_id),
                version,
                str(run_id),
                version,
                actor,
                run_type,
                _json({"run_id": str(run_id), "state": run_state}),
                NOW,
            )
        yield (
            "plan",
            str(PLAN_ID),
            version,
            None,
            None,
            actor,
            "plan.revised",
            _json({"plan_id": str(PLAN_ID), "revision": version}),
            NOW,
        )
        yield (
            "workspace",
            str(WORKSPACE_ID),
            version,
            None,
            None,
            actor,
            "budget.updated",
            _json({"sequence": version}),
            NOW,
        )


def _parse_frame(frame: str) -> tuple[int, str, dict[str, Any]]:
    fields: dict[str, str] = {}
    for line in frame.splitlines():
        if ": " in line:
            name, value = line.split(": ", 1)
            fields[name] = value
    if set(fields) != {"id", "event", "data"}:
        raise AssertionError(f"unexpected SSE frame fields: {fields!r}")
    payload = json.loads(fields["data"])
    event_id = int(fields["id"])
    if payload["id"] != event_id or payload["type"] != fields["event"]:
        raise AssertionError("SSE id/type does not match serialized Event")
    return event_id, fields["event"], payload


class GateProjection:
    """Small consumer-side projection used to verify replay convergence."""

    def __init__(self) -> None:
        self.last_event_id = 0
        self.event_count = 0
        self.event_ids: list[int] = []
        self.event_types: Counter[str] = Counter()
        self.aggregate_versions: dict[tuple[str, str], int] = {}
        self.run_sequences: dict[str, int] = {}
        self.run_states: dict[str, str] = {}
        self.latest_plan_revision = 0
        self.latest_budget_sequence = 0

    def apply(self, event_id: int, event_type: str, event: dict[str, Any]) -> None:
        if event_id <= self.last_event_id:
            raise AssertionError("Event IDs must be strictly increasing")
        self.last_event_id = event_id
        self.event_count += 1
        self.event_ids.append(event_id)
        self.event_types[event_type] += 1

        aggregate_key = (event["aggregate_type"], event["aggregate_id"])
        expected_version = self.aggregate_versions.get(aggregate_key, 0) + 1
        if event["aggregate_version"] != expected_version:
            raise AssertionError(
                f"aggregate version gap for {aggregate_key}: "
                f"expected {expected_version}, got {event['aggregate_version']}"
            )
        self.aggregate_versions[aggregate_key] = expected_version

        run_id = event["run_id"]
        if run_id is not None:
            expected_run_seq = self.run_sequences.get(run_id, 0) + 1
            if event["run_seq"] != expected_run_seq:
                raise AssertionError(
                    f"Run sequence gap for {run_id}: "
                    f"expected {expected_run_seq}, got {event['run_seq']}"
                )
            self.run_sequences[run_id] = expected_run_seq
            if event_type != "run.heartbeat":
                self.run_states[run_id] = event["payload"]["state"]

        if event_type == "plan.revised":
            self.latest_plan_revision = event["payload"]["revision"]
        elif event_type == "budget.updated":
            self.latest_budget_sequence = event["payload"]["sequence"]

    def ui_snapshot(self) -> dict[str, object]:
        return {
            "last_event_id": self.last_event_id,
            "event_count": self.event_count,
            "event_types": dict(sorted(self.event_types.items())),
            "run_states": dict(sorted(self.run_states.items())),
            "latest_plan_revision": self.latest_plan_revision,
            "latest_budget_sequence": self.latest_budget_sequence,
        }


class BoundedASGIStream:
    """Drive one authenticated streaming request with one-frame backpressure."""

    def __init__(self, app: Any, *, last_event_id: int) -> None:
        self.app = app
        self.last_event_id = last_event_id
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=1
        )
        self._task: asyncio.Task[None] | None = None
        self.response_start: dict[str, Any] | None = None

    async def open(self) -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/events",
            "raw_path": b"/api/v1/events",
            "query_string": b"",
            "headers": [
                (b"host", b"127.0.0.1:43124"),
                (b"origin", ORIGIN.encode("ascii")),
                (b"authorization", f"Bearer {TOKEN}".encode("ascii")),
                (
                    b"last-event-id",
                    str(self.last_event_id).encode("ascii"),
                ),
            ],
            "client": ("127.0.0.1", 50001),
            "server": ("127.0.0.1", 43124),
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
            timeout=2,
        )
        if self.response_start["type"] != "http.response.start":
            raise AssertionError(self.response_start)

    async def next_frame(self) -> str:
        while True:
            message = await asyncio.wait_for(
                self._send_queue.get(),
                timeout=2,
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
            await asyncio.wait_for(self._task, timeout=2)
        except asyncio.TimeoutError:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)


class D1RuntimeGateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "nana.db"
        self.connection = initialize_database(self.database_path)
        self._insert_fixture()
        stream = SQLiteEventStream(
            self.database_path,
            poll_interval=0.001,
            batch_size=1024,
        )
        self.app = create_runtime_app(
            event_stream=stream,
            local_session=LocalSession(token=TOKEN, origin=ORIGIN),
        )

    async def asyncTearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _insert_fixture(self) -> None:
        self.connection.execute(
            """
            INSERT INTO workspaces (
                id, schema_version, data_root, policy_json, status,
                revision, created_at
            ) VALUES (?, 1, 'workspace', '{}', 'active', 1, ?)
            """,
            (str(WORKSPACE_ID), NOW),
        )
        self.connection.execute(
            """
            INSERT INTO projects (
                id, workspace_id, title, status, data_class, revision,
                created_at
            ) VALUES (?, ?, 'D1 gate', 'active', 'public', 1, ?)
            """,
            (str(PROJECT_ID), str(WORKSPACE_ID), NOW),
        )
        self.connection.execute(
            """
            INSERT INTO inquiries (
                id, project_id, question, acceptance, status, revision,
                created_at
            ) VALUES (?, ?, 'Replay?', 'No gaps', 'active', 1, ?)
            """,
            (str(INQUIRY_ID), str(PROJECT_ID), NOW),
        )
        self.connection.execute(
            """
            INSERT INTO plans (
                id, inquiry_id, revision, status, steps_json, policy_json,
                budget_json, created_at
            ) VALUES (?, ?, ?, 'completed', '[]', '{}', '{}', ?)
            """,
            (
                str(PLAN_ID),
                str(INQUIRY_ID),
                VERSIONS_PER_AGGREGATE,
                NOW,
            ),
        )
        self.connection.executemany(
            """
            INSERT INTO runs (
                id, project_id, inquiry_id, state, snapshot_json,
                result_json, created_at, finished_at
            ) VALUES (?, ?, ?, 'succeeded', '{}', '{}', ?, ?)
            """,
            (
                (
                    str(run_id),
                    str(PROJECT_ID),
                    str(INQUIRY_ID),
                    NOW,
                    NOW,
                )
                for run_id in RUN_IDS
            ),
        )
        self.connection.executemany(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version,
                run_id, run_seq, actor_json, type, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _event_rows(),
        )
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) "
            "SELECT id FROM events ORDER BY id"
        )
        self.connection.commit()

    async def _consume(
        self,
        projection: GateProjection,
        *,
        count: int,
    ) -> None:
        opened = BoundedASGIStream(
            self.app,
            last_event_id=projection.last_event_id,
        )
        await opened.open()
        try:
            self.assertEqual(opened.response_start["status"], 200)
            headers = dict(opened.response_start["headers"])
            self.assertTrue(
                headers[b"content-type"].startswith(b"text/event-stream")
            )
            for _ in range(count):
                projection.apply(*_parse_frame(await opened.next_frame()))
        finally:
            await opened.close()

    async def test_ten_thousand_mixed_events_converge_after_reconnects(
        self,
    ) -> None:
        expected_ids = [
            int(row["id"])
            for row in self.connection.execute(
                "SELECT id FROM events ORDER BY id"
            ).fetchall()
        ]
        self.assertEqual(len(expected_ids), EVENT_COUNT)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM outbox_events"
            ).fetchone()[0],
            EVENT_COUNT,
        )

        projection = GateProjection()
        for segment_size in (3_333, 4_444, 2_223):
            await self._consume(projection, count=segment_size)

        self.assertEqual(projection.event_count, EVENT_COUNT)
        self.assertEqual(projection.event_ids, expected_ids)
        self.assertEqual(projection.last_event_id, expected_ids[-1])
        self.assertEqual(
            projection.aggregate_versions,
            {
                ("run", str(RUN_IDS[0])): VERSIONS_PER_AGGREGATE,
                ("run", str(RUN_IDS[1])): VERSIONS_PER_AGGREGATE,
                ("plan", str(PLAN_ID)): VERSIONS_PER_AGGREGATE,
                ("workspace", str(WORKSPACE_ID)): VERSIONS_PER_AGGREGATE,
            },
        )
        self.assertEqual(
            projection.run_sequences,
            {
                str(RUN_IDS[0]): VERSIONS_PER_AGGREGATE,
                str(RUN_IDS[1]): VERSIONS_PER_AGGREGATE,
            },
        )
        canonical_run_states = {
            str(row["id"]): str(row["state"])
            for row in self.connection.execute(
                "SELECT id, state FROM runs ORDER BY id"
            ).fetchall()
        }
        self.assertEqual(projection.run_states, canonical_run_states)
        self.assertEqual(
            projection.ui_snapshot(),
            {
                "last_event_id": expected_ids[-1],
                "event_count": EVENT_COUNT,
                "event_types": {
                    "budget.updated": VERSIONS_PER_AGGREGATE,
                    "plan.revised": VERSIONS_PER_AGGREGATE,
                    "run.created": 2,
                    "run.heartbeat": 4_994,
                    "run.started": 2,
                    "run.succeeded": 2,
                },
                "run_states": {
                    str(RUN_IDS[0]): "succeeded",
                    str(RUN_IDS[1]): "succeeded",
                },
                "latest_plan_revision": VERSIONS_PER_AGGREGATE,
                "latest_budget_sequence": VERSIONS_PER_AGGREGATE,
            },
        )


if __name__ == "__main__":
    unittest.main()
