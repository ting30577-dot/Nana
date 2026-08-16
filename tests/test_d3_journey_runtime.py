"""D3-05 authenticated HTTP and owner-lane mutation tests."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter
from unittest.mock import patch

from nana_sidecar.contracts.common import ActorRef
from nana_sidecar.contracts.errors import ErrorCode
from nana_sidecar.contracts.journey import JOURNEY_COMMAND_NAMES, JourneyCommandRequest
from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    load_dev_journey,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.runtime_app import (
    SCHEMA_READ_CEILING,
    SCHEMA_VERSION,
    JourneyRuntimeConfig,
    RuntimeConfigurationError,
    create_runtime_app,
    validate_runtime_route_inventory,
)
from nana_sidecar.sse import LocalSession, SQLiteEventStream
from nana_sidecar.storage.command_transactions import CommandExecutionError
from nana_sidecar.storage.database import initialize_database
from nana_sidecar.storage.journey_commands import JourneyCommandService
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


ORIGIN = "http://127.0.0.1:43123"
TOKEN = "d3-session-" + ("b" * 43)
REQUESTS = TypeAdapter(JourneyCommandRequest)


class D3JourneyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = WorkspaceRuntime(Path(self.tempdir.name) / "nana.db")
        self.definition = read_dev_journey_definition()
        self.session = LocalSession(token=TOKEN, origin=ORIGIN)
        self.app = create_runtime_app(
            workspace_runtime=self.workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-08T00:00:01Z",
            ),
        )

    async def asyncTearDown(self) -> None:
        if self.workspace.state == "ready":
            control = self.app.state.runtime_control
            await control.close()
        self.tempdir.cleanup()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Host": "127.0.0.1:43123",
            "Origin": ORIGIN,
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }

    def project_payload(self, *, command_id: str | None = None) -> dict[str, object]:
        return {
            "type": "CreateProject",
            "command_id": command_id or str(uuid4()),
            "expected_revision": 1,
            "workspace_id": self.definition["workspace"]["id"],
            "title": "HTTP-created project",
            "data_class": "public",
        }

    async def test_handshake_and_route_inventory_keep_external_effects_disabled(self) -> None:
        mutations = {
            (route.path, method)
            for route in self.app.routes
            for method in getattr(route, "methods", set())
            if method in {"POST", "PUT", "PATCH", "DELETE"}
        }
        self.assertEqual(mutations, {("/api/v1/journey/commands", "POST")})
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.get("/api/v1/handshake", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body["enabled_mutations"]),
            set(JOURNEY_COMMAND_NAMES) - {"RequestApproval", "DecideApproval"},
        )
        self.assertTrue(body["mutations_enabled"])
        self.assertTrue(body["execution_enabled"])
        self.assertFalse(body["external_effects_enabled"])
        self.assertEqual(body["schema_version"], SCHEMA_VERSION)
        self.assertEqual(body["schema_read_ceiling"], SCHEMA_READ_CEILING)

    def test_checked_in_openapi_is_the_mutation_runtime_authority(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked_in = json.loads(
            (root / "nana_web" / "openapi.json").read_text(encoding="utf-8")
        )
        self.assertEqual(checked_in, self.app.openapi())
        operation = checked_in["paths"]["/api/v1/journey/commands"]["post"]
        self.assertEqual(operation["security"], [{"LocalSessionBearer": []}])
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        mapping = request_schema["discriminator"]["mapping"]
        self.assertEqual(set(mapping), set(JOURNEY_COMMAND_NAMES))
        self.assertEqual(len(request_schema["oneOf"]), len(JOURNEY_COMMAND_NAMES))
        for reference in mapping.values():
            schema_name = reference.rsplit("/", 1)[1]
            schema = checked_in["components"]["schemas"][schema_name]
            self.assertNotIn("actor", schema["properties"])
            self.assertIn("expected_revision", schema["required"])
        self.assertNotIn("CreateWorkspace", mapping)
        self.assertIn("StartRun", mapping)
        self.assertIn("CancelRun", mapping)
        self.assertIn("RequestApproval", mapping)
        self.assertIn("DecideApproval", mapping)
        request_approval = checked_in["components"]["schemas"]["RequestApprovalRequest"]
        self.assertEqual(
            set(request_approval["properties"]),
            {"type", "command_id", "expected_revision", "finding_id", "target_selection_id"},
        )
        responses = checked_in["paths"]["/api/v1/journey/commands"]["post"]["responses"]
        for status in ("409", "422", "500"):
            self.assertEqual(
                responses[status]["content"]["application/json"]["schema"]["$ref"],
                "#/components/schemas/ErrorResponse",
            )

    def test_duplicate_mutation_route_fails_exact_inventory(self) -> None:
        @self.app.post("/api/v1/journey/commands", include_in_schema=False)
        def duplicate_route() -> dict[str, bool]:
            return {"duplicate": True}

        with self.assertRaises(RuntimeConfigurationError):
            validate_runtime_route_inventory(self.app, journey_enabled=True)

    def test_mutation_runtime_rejects_actor_without_stable_id(self) -> None:
        with self.assertRaisesRegex(RuntimeConfigurationError, "stable"):
            create_runtime_app(
                workspace_runtime=WorkspaceRuntime(Path(self.tempdir.name) / "actor.db"),
                local_session=self.session,
                journey_runtime=JourneyRuntimeConfig(
                    bootstrap=workspace_bootstrap_spec(self.definition),
                    actor=ActorRef(kind="user"),
                    resources=(frozen_resource_descriptor(self.definition),),
                ),
            )

    async def test_server_injects_actor_and_projection_observes_committed_fact(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(self.project_payload()),
                )
                snapshot = await client.get("/api/v1/bootstrap", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "accepted")
            projection = snapshot.json()
            self.assertGreaterEqual(projection["high_water_event_id"], 2)
            self.assertIn(
                "project.created",
                {event["type"] for event in projection["activity"]},
            )
            actor = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute(
                    "SELECT actor_json FROM command_log"
                ).fetchone()[0]
            )
            self.assertEqual(
                json.loads(actor),
                {"kind": "user", "id": "local-session-user", "version": None},
            )

    async def test_http_response_loss_after_commit_replays_stored_result(self) -> None:
        payload = self.project_payload()
        async with self.app.router.lifespan_context(self.app):
            control = self.app.state.runtime_control
            original = type(control).execute_journey
            calls = 0

            async def lose_response(owner, command: JourneyCommandRequest):
                nonlocal calls
                result = await original(owner, command)
                if calls == 0:
                    calls += 1
                    raise RuntimeError("simulated HTTP response loss")
                return result

            with patch.object(type(control), "execute_journey", new=lose_response):
                async with AsyncClient(
                    transport=ASGITransport(app=self.app), base_url=ORIGIN
                ) as client:
                    first = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps(payload),
                    )
                    second = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps(payload),
                    )
        self.assertEqual(first.status_code, 500)
        self.assertEqual(first.json()["error"]["code"], "E_INTERNAL")
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["status"], "replayed")
        self.assertEqual(second.json()["command_id"], payload["command_id"])

    async def test_http_conflict_returns_structured_error_response(self) -> None:
        payload = {
            "type": "CreateInquiry",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "project_id": str(uuid4()),
            "question": "missing project",
            "acceptance": "must return a structured conflict",
        }
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(payload),
                )
        self.assertEqual(response.status_code, 409, response.text)
        body = response.json()
        self.assertEqual(body["error"]["code"], "E_REVISION_CONFLICT")
        self.assertIn("category", body["error"])

    async def test_committed_mutation_is_visible_to_sse_outbox_stream(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(self.project_payload()),
                )
            self.assertEqual(response.status_code, 200, response.text)
            stream = SQLiteEventStream(self.workspace.database_path, poll_interval=0.01)
            events = stream.iter_sse(after_id=1)
            frame = await asyncio.wait_for(events.__anext__(), timeout=1)
            await events.aclose()
        self.assertIn("event: project.created", frame)
        self.assertIn("id:", frame)

    async def test_actor_and_non_curated_command_fail_before_dispatch(self) -> None:
        actor_payload = self.project_payload()
        actor_payload["actor"] = {"kind": "user", "id": "browser-chosen"}
        start_run = {
            "type": "StartRun",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "actor": {"kind": "user", "id": "browser-chosen"},
            "project_id": str(uuid4()),
            "inquiry_id": str(uuid4()),
            "plan_id": str(uuid4()),
            "plan_revision": 1,
            "backend": {"id": "python.unittest.locked", "version": "1"},
            "random_seed": 0,
        }
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                for payload in (actor_payload, start_run):
                    response = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps(payload),
                    )
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertIn("error", response.json())
                    self.assertIn("code", response.json()["error"])
            count = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute(
                    "SELECT COUNT(*) FROM command_log"
                ).fetchone()[0]
            )
            self.assertEqual(count, 0)

    async def test_exact_body_boundary_is_accepted_and_larger_body_is_rejected(self) -> None:
        encoded = json.dumps(self.project_payload(), separators=(",", ":")).encode("utf-8")
        exact = encoded + (b" " * ((64 * 1024) - len(encoded)))
        too_large = exact + b" "
        self.assertEqual(len(exact), 64 * 1024)
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                accepted = await client.post(
                    "/api/v1/journey/commands", headers=self.headers, content=exact
                )
                rejected = await client.post(
                    "/api/v1/journey/commands", headers=self.headers, content=too_large
                )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(rejected.status_code, 413)

    async def test_concurrent_same_command_has_one_effect_and_one_replay(self) -> None:
        payload = json.dumps(self.project_payload())
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                first, second = await asyncio.gather(*(
                    client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=payload,
                    )
                    for _ in range(2)
                ))
            self.assertEqual({first.status_code, second.status_code}, {200})
            self.assertEqual(
                {first.json()["status"], second.json()["status"]},
                {"accepted", "replayed"},
            )
            counts = await self.app.state.runtime_control._run_on_writer(
                lambda: (
                    self.workspace.connection.execute(
                        "SELECT COUNT(*) FROM projects"
                    ).fetchone()[0],
                    self.workspace.connection.execute(
                        "SELECT COUNT(*) FROM events WHERE type = 'project.created'"
                    ).fetchone()[0],
                    self.workspace.connection.execute(
                        "SELECT COUNT(*) FROM command_log"
                    ).fetchone()[0],
                )
            )
            self.assertEqual(counts, (1, 1, 1))

    async def test_different_command_ids_racing_same_active_edge_are_serialized(self) -> None:
        for round_index in range(20):
            race_workspace = WorkspaceRuntime(
                Path(self.tempdir.name) / f"race-{round_index}.db"
            )
            race_app = create_runtime_app(
                workspace_runtime=race_workspace,
                local_session=self.session,
                journey_runtime=JourneyRuntimeConfig(
                    bootstrap=workspace_bootstrap_spec(self.definition),
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-08T00:00:01Z",
                ),
            )
            async with race_app.router.lifespan_context(race_app):
                def seed() -> tuple[dict[str, str], str, int]:
                    connection = race_workspace.connection
                    service = JourneyCommandService(
                        connection,
                        actor=local_fixture_actor(),
                        resources=(frozen_resource_descriptor(self.definition),),
                        now=lambda: "2026-08-08T00:00:01Z",
                    )
                    loaded = load_dev_journey(service, self.definition)
                    claim = service.execute(REQUESTS.validate_python({
                        "type": "CreateClaim", "command_id": str(uuid4()),
                        "expected_revision": 1, "inquiry_id": str(loaded.ids["inquiry"]),
                        "statement": f"Concurrent edge target {round_index}",
                    }))
                    claim_id = next(
                        value.split(":", 1)[1]
                        for value in claim.affected_revisions
                        if value.startswith("claim:")
                    )
                    relation_count = connection.execute(
                        "SELECT COUNT(*) FROM relations"
                    ).fetchone()[0]
                    return {name: str(value) for name, value in loaded.ids.items()}, claim_id, relation_count

                ids, claim_id, relation_count = await race_app.state.runtime_control._run_on_writer(seed)
                common = {
                    "type": "CreateRelation",
                    "expected_revision": 1,
                    "relation_type": "evidence_supports_claim",
                    "source_type": "evidence",
                    "source_id": ids["evidence"],
                    "target_type": "claim",
                    "target_id": claim_id,
                }
                requests = [
                    REQUESTS.validate_python({**common, "command_id": str(uuid4())})
                    for _ in range(8)
                ]
                barrier = asyncio.Barrier(len(requests))
                ready_count = 0

                async def execute_with_jitter(index: int, request: JourneyCommandRequest):
                    nonlocal ready_count
                    ready_count += 1
                    await barrier.wait()
                    await asyncio.sleep((index % 3) * 0.001)
                    return await race_app.state.runtime_control.execute_journey(request)

                results = await asyncio.gather(
                    *(execute_with_jitter(index, request) for index, request in enumerate(requests)),
                    return_exceptions=True,
                )
                accepted = [result for result in results if getattr(result, "status", None) == "accepted"]
                rejected = [result for result in results if isinstance(result, CommandExecutionError)]
                self.assertEqual(len(accepted), 1)
                self.assertEqual(len(rejected), len(requests) - 1)
                self.assertEqual(ready_count, len(requests))
                self.assertEqual(len(accepted[0].event_ids), 1)
                self.assertTrue(all(
                    error.error.code is ErrorCode.RELATION_INVALID
                    and error.error.details.get("reason") == "duplicate_active_relation"
                    for error in rejected
                ))
                final_count = await race_app.state.runtime_control._run_on_writer(
                    lambda: race_workspace.connection.execute(
                        "SELECT COUNT(*) FROM relations"
                    ).fetchone()[0]
                )
                self.assertEqual(final_count, relation_count + 1)

    async def test_chunked_body_without_length_and_lying_length_are_handled(self) -> None:
        body = json.dumps(self.project_payload(), separators=(",", ":")).encode()
        async with self.app.router.lifespan_context(self.app):
            accepted = await self._raw_post(
                headers=[
                    (b"host", b"127.0.0.1:43123"),
                    (b"origin", ORIGIN.encode()),
                    (b"authorization", f"Bearer {TOKEN}".encode()),
                    (b"content-type", b"application/json"),
                ],
                chunks=(body[:17], body[17:]),
            )
            rejected = await self._raw_post(
                headers=[
                    (b"host", b"127.0.0.1:43123"),
                    (b"origin", ORIGIN.encode()),
                    (b"authorization", f"Bearer {TOKEN}".encode()),
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body) - 1).encode()),
                ],
                chunks=(body,),
            )
        self.assertEqual(accepted, 200)
        self.assertEqual(rejected, 400)

    async def test_duplicate_security_headers_fail_closed(self) -> None:
        body = json.dumps(self.project_payload(), separators=(",", ":")).encode()
        base = [
            (b"host", b"127.0.0.1:43123"),
            (b"origin", ORIGIN.encode()),
            (b"authorization", f"Bearer {TOKEN}".encode()),
            (b"content-type", b"application/json"),
        ]
        cases = (
            (base + [(b"authorization", f"Bearer {TOKEN}".encode())], 401),
            (base + [(b"origin", ORIGIN.encode())], 403),
            (base + [(b"host", b"127.0.0.1:43123")], 403),
            (
                base + [
                    (b"content-length", str(len(body)).encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
                400,
            ),
        )
        async with self.app.router.lifespan_context(self.app):
            for headers, expected in cases:
                with self.subTest(expected=expected):
                    self.assertEqual(
                        await self._raw_post(headers=headers, chunks=(body,)),
                        expected,
                    )

    async def test_authentication_happens_before_body_receive(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            sent: list[dict[str, object]] = []

            async def forbidden_receive() -> dict[str, object]:
                raise AssertionError("unauthorized request body was consumed")

            async def send(message: dict[str, object]) -> None:
                sent.append(message)

            await self.app(
                {
                    "type": "http",
                    "asgi": {"version": "3.0"},
                    "http_version": "1.1",
                    "method": "POST",
                    "scheme": "http",
                    "path": "/api/v1/journey/commands",
                    "raw_path": b"/api/v1/journey/commands",
                    "query_string": b"",
                    "headers": [
                        (b"host", b"127.0.0.1:43123"),
                        (b"origin", ORIGIN.encode("ascii")),
                        (b"content-type", b"application/json"),
                        (b"content-length", b"999999"),
                    ],
                    "client": ("127.0.0.1", 50000),
                    "server": ("127.0.0.1", 43123),
                },
                forbidden_receive,
                send,
            )
        starts = [message for message in sent if message["type"] == "http.response.start"]
        self.assertEqual(starts[0]["status"], 401)

    async def test_mutation_content_contract_and_preflight_are_exact(self) -> None:
        payload = json.dumps(self.project_payload())
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                preflight = await client.options(
                    "/api/v1/journey/commands",
                    headers={
                        "Origin": ORIGIN,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "authorization, content-type",
                    },
                )
                wrong_type = await client.post(
                    "/api/v1/journey/commands",
                    headers={**self.headers, "Content-Type": "application/json; charset=utf-8"},
                    content=payload,
                )
                encoded = await client.post(
                    "/api/v1/journey/commands",
                    headers={**self.headers, "Content-Encoding": "gzip"},
                    content=payload,
                )
                forwarded = await client.post(
                    "/api/v1/journey/commands",
                    headers={**self.headers, "X-Forwarded-Host": "127.0.0.1:43123"},
                    content=payload,
                )
        self.assertEqual(preflight.status_code, 204)
        self.assertEqual(wrong_type.status_code, 415)
        self.assertEqual(encoded.status_code, 415)
        self.assertEqual(forwarded.status_code, 400)

    async def test_every_cross_origin_mutation_is_rejected_before_writes(self) -> None:
        payload = json.dumps(self.project_payload())
        before = None
        async with self.app.router.lifespan_context(self.app):
            before = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute("SELECT COUNT(*) FROM command_log").fetchone()[0]
            )
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                for hostile_origin in (
                    "http://127.0.0.1:9", "http://localhost:43123",
                    "http://evil.invalid", "null",
                ):
                    response = await client.post(
                        "/api/v1/journey/commands",
                        headers={**self.headers, "Origin": hostile_origin},
                        content=payload,
                    )
                    self.assertEqual(response.status_code, 403, hostile_origin)
                rebound = await client.post(
                    "/api/v1/journey/commands",
                    headers={**self.headers, "Host": "localhost:43123"},
                    content=payload,
                )
                self.assertEqual(rebound.status_code, 403)
            after = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute("SELECT COUNT(*) FROM command_log").fetchone()[0]
            )
        self.assertEqual(after, before)

    async def test_sqlite_connection_rejects_access_outside_owner_lane(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            with self.assertRaises(sqlite3.ProgrammingError):
                self.workspace.connection.execute("SELECT 1")
        self.assertEqual(self.workspace.state, "closed")

    async def test_prestarted_readonly_workspace_closes_on_its_owner_thread(self) -> None:
        path = Path(self.tempdir.name) / "prestarted.db"
        workspace = WorkspaceRuntime(path)
        workspace.start()
        app = create_runtime_app(workspace_runtime=workspace, local_session=self.session)
        async with app.router.lifespan_context(app):
            self.assertEqual(workspace.state, "ready")
        self.assertEqual(workspace.state, "closed")

    async def test_second_mutation_control_shuts_down_after_shared_owner_rejection(self) -> None:
        workspace = WorkspaceRuntime(Path(self.tempdir.name) / "shared.db")
        config = JourneyRuntimeConfig(
            bootstrap=workspace_bootstrap_spec(self.definition),
            actor=local_fixture_actor(),
            resources=(frozen_resource_descriptor(self.definition),),
        )
        first = create_runtime_app(
            workspace_runtime=workspace,
            local_session=self.session,
            journey_runtime=config,
        )
        second = create_runtime_app(
            workspace_runtime=workspace,
            local_session=self.session,
            journey_runtime=config,
        )
        async with first.router.lifespan_context(first):
            with self.assertRaises(RuntimeConfigurationError):
                async with second.router.lifespan_context(second):
                    pass
        self.assertTrue(second.state.runtime_control.writer_executor._shutdown)

    async def test_bootstrap_failure_closes_sqlite_and_releases_workspace_lock(self) -> None:
        path = Path(self.tempdir.name) / "bootstrap-failure.db"
        connection = initialize_database(path)
        connection.execute(
            "INSERT INTO workspaces(id, schema_version, data_root, policy_json, status, revision, created_at) "
            "VALUES (?, 7, 'workspace', '{}', 'active', 1, ?)",
            (str(uuid4()), "2026-08-08T00:00:00Z"),
        )
        connection.commit()
        connection.close()
        workspace = WorkspaceRuntime(path)
        app = create_runtime_app(
            workspace_runtime=workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "mismatch"):
            async with app.router.lifespan_context(app):
                pass
        self.assertEqual(workspace.state, "closed")
        self.assertIsNone(workspace.connection)
        replacement = WorkspaceRuntime(path)
        replacement.start()
        replacement.close()

    async def _raw_post(
        self,
        *,
        headers: list[tuple[bytes, bytes]],
        chunks: tuple[bytes, ...],
    ) -> int:
        pending = list(chunks)
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            body = pending.pop(0)
            return {
                "type": "http.request",
                "body": body,
                "more_body": bool(pending),
            }

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        await self.app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/v1/journey/commands",
                "raw_path": b"/api/v1/journey/commands",
                "query_string": b"",
                "headers": headers,
                "client": ("127.0.0.1", 50000),
                "server": ("127.0.0.1", 43123),
            },
            receive,
            send,
        )
        starts = [message for message in sent if message["type"] == "http.response.start"]
        return int(starts[0]["status"])


if __name__ == "__main__":
    unittest.main()
