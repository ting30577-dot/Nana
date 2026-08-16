"""D3-02 authenticated runtime authority gate."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
import socket
import subprocess
import sys
import time
import json

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, get
from unittest.mock import patch

from nana_sidecar.app import create_app
from nana_sidecar.runtime_app import (
    JourneyRuntimeConfig,
    RuntimeConfigurationError,
    create_runtime_app,
    validate_no_mutation_methods,
)
from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime
from tests.test_d1_http_sse import OpenASGIStream


ORIGIN = "http://127.0.0.1:43123"
TOKEN = "d1-session-" + ("a" * 43)


class D3RuntimeAuthorityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = WorkspaceRuntime(Path(self.tempdir.name) / "nana.db")
        self.session = LocalSession(token=TOKEN, origin=ORIGIN)
        self.app = create_runtime_app(
            workspace_runtime=self.workspace,
            local_session=self.session,
        )

    async def asyncTearDown(self) -> None:
        if self.workspace.state == "ready":
            self.workspace.close()
        self.tempdir.cleanup()

    @property
    def headers(self) -> dict[str, str]:
        return {"Host": "127.0.0.1:43123", "Origin": ORIGIN, "Authorization": f"Bearer {TOKEN}"}

    async def test_health_is_the_only_public_route_before_lifespan_ready(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=self.app), base_url=ORIGIN
        ) as client:
            health = await client.get("/healthz")
            handshake = await client.get("/api/v1/handshake")
            docs = await client.get("/docs")
        self.assertEqual(health.status_code, 503)
        self.assertEqual(health.json(), {"status": "starting"})
        self.assertEqual(handshake.status_code, 503)
        self.assertEqual(docs.status_code, 503)

    async def test_all_runtime_reads_require_exact_session_origin_and_host(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                self.assertEqual((await client.get("/healthz")).status_code, 200)
                for path in ("/api/v1/handshake", "/api/v1/contracts", "/api/v1/bootstrap", "/openapi.json"):
                    with self.subTest(path=path):
                        self.assertEqual((await client.get(path)).status_code, 401)
                        self.assertEqual((await client.get(path, headers={"Host": "127.0.0.1:43123", "Origin": ORIGIN})).status_code, 401)
                        wrong_host = dict(self.headers, Host="127.0.0.1:43124")
                        self.assertEqual((await client.get(path, headers=wrong_host)).status_code, 403)
                        wrong_origin = dict(self.headers, Origin="http://localhost:43123")
                        self.assertEqual((await client.get(path, headers=wrong_origin)).status_code, 403)
                        self.assertEqual((await client.get(path, headers=self.headers)).status_code, 200)
                        browser_fetch = {
                            "Host": "127.0.0.1:43123",
                            "Authorization": f"Bearer {TOKEN}",
                            "Sec-Fetch-Site": "same-origin",
                            "Sec-Fetch-Mode": "cors",
                            "Sec-Fetch-Dest": "empty",
                        }
                        self.assertEqual(
                            (await client.get(path, headers=browser_fetch)).status_code,
                            200,
                        )
                        browser_fetch["Sec-Fetch-Site"] = "cross-site"
                        self.assertEqual(
                            (await client.get(path, headers=browser_fetch)).status_code,
                            403,
                        )
                self.assertEqual((await client.get("/docs", headers=self.headers)).status_code, 404)
                self.assertEqual((await client.get("/api/v1/contracts/", headers=self.headers)).status_code, 404)

    async def test_preflight_is_exact_and_no_mutation_route_exists(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                accepted = await client.options(
                    "/api/v1/events",
                    headers={
                        "Origin": ORIGIN,
                        "Access-Control-Request-Method": "GET",
                        "Access-Control-Request-Headers": "authorization, last-event-id",
                    },
                )
                rejected = await client.options(
                    "/api/v1/events",
                    headers={
                        "Origin": ORIGIN,
                        "Access-Control-Request-Method": "GET",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
            self.assertEqual(accepted.status_code, 204)
            self.assertEqual(accepted.headers["access-control-allow-origin"], ORIGIN)
            self.assertNotEqual(rejected.status_code, 204)
        methods = {
            method
            for route in self.app.routes
            for method in getattr(route, "methods", set())
            if method in {"POST", "PUT", "PATCH", "DELETE"}
        }
        self.assertEqual(methods, set())

    async def test_runtime_rejects_future_approval_and_export_commands_before_writes(self) -> None:
        forbidden = (
            "RequestApproval",
            "DecideApproval",
            "AuthorizeAction",
            "PublishExport",
            "ConsumeApproval",
        )
        definition = read_dev_journey_definition()
        configured_workspace = WorkspaceRuntime(
            Path(self.tempdir.name) / "configured-journey.db"
        )
        configured_session = LocalSession(
            token="d3-configured-session-" + ("c" * 43), origin=ORIGIN
        )
        configured_app = create_runtime_app(
            workspace_runtime=configured_workspace,
            local_session=configured_session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(definition),),
                now=lambda: "2026-08-10T00:00:01Z",
            ),
        )
        configured_headers = {
            "Host": "127.0.0.1:43123",
            "Origin": ORIGIN,
            "Authorization": f"Bearer {configured_session.token.get_secret_value()}",
            "Content-Type": "application/json",
        }
        async with configured_app.router.lifespan_context(configured_app):
            async with AsyncClient(
                transport=ASGITransport(app=configured_app), base_url=ORIGIN
            ) as client:
                for command_type in forbidden:
                    with self.subTest(command_type=command_type):
                        response = await client.post(
                            "/api/v1/journey/commands",
                            headers=configured_headers,
                            json={
                                "type": command_type,
                                "command_id": f"future-{command_type.lower()}",
                                "expected_revision": 1,
                            },
                        )
                        self.assertEqual(response.status_code, 422, response.text)
            command_count = await configured_app.state.runtime_control._run_on_writer(
                lambda: configured_workspace.connection.execute(
                    "SELECT COUNT(*) FROM command_log"
                ).fetchone()[0]
            )
            self.assertEqual(command_count, 0)

    async def test_bootstrap_page_requires_signed_opaque_token(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(transport=ASGITransport(app=self.app), base_url=ORIGIN) as client:
                snapshot = await client.get("/api/v1/bootstrap", headers=self.headers)
                self.assertEqual(snapshot.status_code, 200)
                bad = await client.get(
                    "/api/v1/bootstrap?section=activity&page_token=invalid",
                    headers=self.headers,
                )
                self.assertEqual(bad.status_code, 400)

    async def test_bootstrap_page_token_is_bound_to_the_issuing_runtime_session(self) -> None:
        database_path = Path(self.tempdir.name) / "session-bound-page.db"
        first_workspace = WorkspaceRuntime(database_path)
        first_session = LocalSession(token="d3-page-session-" + ("a" * 43), origin=ORIGIN)
        first_app = create_runtime_app(
            workspace_runtime=first_workspace,
            local_session=first_session,
        )
        first_headers = {
            "Host": "127.0.0.1:43123",
            "Origin": ORIGIN,
            "Authorization": f"Bearer {first_session.token.get_secret_value()}",
        }
        with patch("nana_sidecar.read_models.MAX_BOOTSTRAP_BYTES", 1):
            async with first_app.router.lifespan_context(first_app):
                async with AsyncClient(
                    transport=ASGITransport(app=first_app), base_url=ORIGIN
                ) as client:
                    oversized = await client.get("/api/v1/bootstrap", headers=first_headers)
        self.assertEqual(oversized.status_code, 413)
        token = oversized.json()["detail"]["page_tokens"]["activity"]

        second_workspace = WorkspaceRuntime(database_path)
        second_session = LocalSession(token="d3-page-session-" + ("b" * 43), origin=ORIGIN)
        second_app = create_runtime_app(
            workspace_runtime=second_workspace,
            local_session=second_session,
        )
        second_headers = {
            "Host": "127.0.0.1:43123",
            "Origin": ORIGIN,
            "Authorization": f"Bearer {second_session.token.get_secret_value()}",
        }
        async with second_app.router.lifespan_context(second_app):
            async with AsyncClient(
                transport=ASGITransport(app=second_app), base_url=ORIGIN
            ) as client:
                replayed = await client.get(
                    "/api/v1/bootstrap",
                    params={"section": "activity", "page_token": token},
                    headers=second_headers,
                )
        self.assertEqual(replayed.status_code, 400)
        self.assertEqual(replayed.json()["detail"]["code"], "E_PAGE_TOKEN")

    async def test_authenticated_manifest_static_surface_has_no_fallback(self) -> None:
        build_root = Path(self.tempdir.name) / "web-dist"
        (build_root / ".vite").mkdir(parents=True)
        (build_root / "assets").mkdir()
        (build_root / "index.html").write_text("<!doctype html><script src='/assets/app.js'></script>", encoding="utf-8")
        (build_root / "assets" / "app.js").write_text("document.body.dataset.ready='true'", encoding="utf-8")
        (build_root / ".vite" / "manifest.json").write_text(
            json.dumps({"index.html": {"file": "assets/app.js", "isEntry": True}}),
            encoding="utf-8",
        )
        workspace = WorkspaceRuntime(Path(self.tempdir.name) / "static.db")
        app = create_runtime_app(
            workspace_runtime=workspace,
            local_session=self.session,
            web_build_root=build_root,
        )
        # Serving is bound to the validated startup bytes, not a later file
        # replacement under the same manifest path.
        (build_root / "assets" / "app.js").write_text("throw new Error('replaced')", encoding="utf-8")
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
                self.assertEqual((await client.get("/")).status_code, 401)
                index = await client.get("/", headers=self.headers)
                asset = await client.get("/assets/app.js", headers=self.headers)
                unknown = await client.get("/assets/unknown.js", headers=self.headers)
                source_map = await client.get("/assets/app.js.map", headers=self.headers)
                config = await client.get("/api/v1/ui-config", headers=self.headers)
        self.assertEqual(index.status_code, 200)
        self.assertIn("default-src 'self'", index.headers["content-security-policy"])
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.text, "document.body.dataset.ready='true'")
        self.assertEqual(asset.headers["x-content-type-options"], "nosniff")
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(source_map.status_code, 404)
        self.assertEqual(config.status_code, 404)

    def test_static_build_manifest_is_bidirectional_and_rejects_source_maps(self) -> None:
        build_root = Path(self.tempdir.name) / "invalid-web"
        (build_root / ".vite").mkdir(parents=True)
        (build_root / "assets").mkdir()
        (build_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        (build_root / "assets" / "app.js").write_text("", encoding="utf-8")
        (build_root / "assets" / "extra.css").write_text("", encoding="utf-8")
        (build_root / ".vite" / "manifest.json").write_text(
            json.dumps({"index.html": {"file": "assets/app.js", "isEntry": True}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeConfigurationError, "do not match"):
            create_runtime_app(
                workspace_runtime=WorkspaceRuntime(Path(self.tempdir.name) / "invalid.db"),
                local_session=self.session,
                web_build_root=build_root,
            )
        (build_root / "assets" / "extra.css").unlink()
        (build_root / "assets" / "app.js.map").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeConfigurationError, "source maps"):
            create_runtime_app(
                workspace_runtime=WorkspaceRuntime(Path(self.tempdir.name) / "invalid-map.db"),
                local_session=self.session,
                web_build_root=build_root,
            )

    def test_static_build_rejects_root_component_reparse_and_route_syntax(self) -> None:
        build_root = Path(self.tempdir.name) / "linked-web"
        (build_root / ".vite").mkdir(parents=True)
        (build_root / "assets").mkdir()
        (build_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        (build_root / "assets" / "app.js").write_text("", encoding="utf-8")
        manifest_path = build_root / ".vite" / "manifest.json"
        manifest_path.write_text(
            json.dumps({"index.html": {"file": "assets/app.js", "isEntry": True}}),
            encoding="utf-8",
        )
        with patch(
            "nana_sidecar.runtime_app._path_is_link_or_reparse",
            side_effect=lambda candidate: Path(candidate) == build_root.absolute(),
        ):
            with self.assertRaisesRegex(RuntimeConfigurationError, "root"):
                create_runtime_app(
                    workspace_runtime=WorkspaceRuntime(Path(self.tempdir.name) / "linked-root.db"),
                    local_session=self.session,
                    web_build_root=build_root,
                )
        with patch(
            "nana_sidecar.runtime_app._path_is_link_or_reparse",
            side_effect=lambda candidate: Path(candidate).name == ".vite",
        ):
            with self.assertRaisesRegex(RuntimeConfigurationError, "metadata"):
                create_runtime_app(
                    workspace_runtime=WorkspaceRuntime(Path(self.tempdir.name) / "linked-component.db"),
                    local_session=self.session,
                    web_build_root=build_root,
                )
        (build_root / "assets" / "{route}.js").write_text("", encoding="utf-8")
        manifest_path.write_text(
            json.dumps({"index.html": {"file": "assets/{route}.js", "isEntry": True}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeConfigurationError, "forbidden asset path"):
            create_runtime_app(
                workspace_runtime=WorkspaceRuntime(Path(self.tempdir.name) / "route-syntax.db"),
                local_session=self.session,
                web_build_root=build_root,
            )

    def test_mutation_guard_rejects_an_injected_route(self) -> None:
        app = FastAPI()

        @app.post("/mutation")
        def mutation() -> dict[str, bool]:
            return {"ok": True}

        with self.assertRaisesRegex(RuntimeConfigurationError, "forbids"):
            validate_no_mutation_methods(app)

    def test_origin_is_single_canonical_ipv4_form(self) -> None:
        for invalid in (
            "http://127.0.0.1:0",
            "http://127.0.0.1:043123",
            "https://127.0.0.1:43123",
            "http://localhost:43123",
            "http://[::1]:43123",
            "http://127.0.0.1:65536",
            "http://127.0.0.1: 43123",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "127.0.0.1"):
                    LocalSession(token=TOKEN, origin=invalid)
        self.assertEqual(LocalSession(token=TOKEN, origin=ORIGIN).authority, "127.0.0.1:43123")

    async def test_failed_startup_exits_after_d3_01_cleanup_and_allows_restart(self) -> None:
        self.workspace._reconcile_artifacts = lambda _connection: (_ for _ in ()).throw(RuntimeError("reconcile failed"))
        with self.assertRaisesRegex(RuntimeError, "reconcile failed"):
            async with self.app.router.lifespan_context(self.app):
                self.fail("failed startup must not yield an application")
        self.assertEqual(self.app.state.runtime_control.state, "failed")
        self.assertEqual(self.workspace.state, "closed")
        replacement = WorkspaceRuntime(self.workspace.database_path)
        replacement.start()
        self.assertEqual(replacement.state, "ready")
        replacement.close()

    async def test_sse_drain_closes_stream_before_workspace_and_timeout_cancels(self) -> None:
        async def exercise(*, ignore_stop: bool) -> list[str]:
            order: list[str] = []

            class RecordingWorkspace(WorkspaceRuntime):
                def close(self) -> None:
                    order.append("workspace.close")
                    super().close()

            class BlockingStream:
                async def iter_sse(self, *, after_id: int, stop_event=None):
                    try:
                        yield "id: 1\nevent: plan.revised\ndata: {}\n\n"
                        if ignore_stop:
                            await asyncio.Event().wait()
                        else:
                            await stop_event.wait()
                    finally:
                        order.append("stream.closed")

            workspace = RecordingWorkspace(Path(self.tempdir.name) / ("timeout.db" if ignore_stop else "drain.db"))
            with patch(
                "nana_sidecar.runtime_app.SQLiteEventStream",
                return_value=BlockingStream(),
            ):
                app = create_runtime_app(
                    workspace_runtime=workspace,
                    local_session=self.session,
                )
            app.state.runtime_control.drain_timeout_seconds = 0.05
            context = app.router.lifespan_context(app)
            await context.__aenter__()
            opened = OpenASGIStream(app, last_event_id=0)
            await opened.open()
            self.assertEqual(await opened.next_frame(), "id: 1\nevent: plan.revised\ndata: {}\n\n")
            await context.__aexit__(None, None, None)
            await opened.close()
            self.assertEqual(workspace.state, "closed")
            return order

        self.assertEqual(await exercise(ignore_stop=False), ["stream.closed", "workspace.close"])
        self.assertEqual(await exercise(ignore_stop=True), ["stream.closed", "workspace.close"])

    def test_runtime_openapi_contains_frozen_d0_contract_surface(self) -> None:
        d0 = create_app().openapi()
        runtime = self.app.openapi()
        for path, operations in d0["paths"].items():
            self.assertIn(path, runtime["paths"])
            self.assertTrue(set(operations) <= set(runtime["paths"][path]))
        d0_schemas = set(d0["components"]["schemas"])
        runtime_schemas = set(runtime["components"]["schemas"])
        self.assertTrue(d0_schemas <= runtime_schemas)
        root = Path(__file__).resolve().parents[1]
        checked_in = json.loads(
            (root / "nana_web" / "openapi.json").read_text(encoding="utf-8")
        )
        for path, operations in runtime["paths"].items():
            self.assertIn(path, checked_in["paths"])
            self.assertTrue(set(operations) <= set(checked_in["paths"][path]))

    def test_real_runtime_process_crash_and_same_workspace_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "nana.db"
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            process_origin = f"http://127.0.0.1:{port}"
            process_headers = {
                "Host": f"127.0.0.1:{port}",
                "Origin": process_origin,
                "Authorization": f"Bearer {TOKEN}",
            }
            script = (
                "import time, uvicorn; "
                "from nana_sidecar.runtime_app import create_runtime_app; "
                "from nana_sidecar.sse import LocalSession; "
                "from nana_sidecar.storage.workspace_lock import WorkspaceRuntime; "
                f"workspace=WorkspaceRuntime({str(database_path)!r}); "
                "original=workspace._reconcile_artifacts; "
                "workspace._reconcile_artifacts=lambda connection: (time.sleep(0.25), original(connection))[1]; "
                f"app=create_runtime_app(workspace_runtime=workspace, local_session=LocalSession(token={TOKEN!r}, origin={process_origin!r})); "
                f"uvicorn.run(app, host='127.0.0.1', port={port}, log_level='critical')"
            )

            def launch() -> subprocess.Popen[str]:
                return subprocess.Popen(
                    [sys.executable, "-c", script],
                    cwd=Path(__file__).resolve().parents[1],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            def await_ready(process: subprocess.Popen[str]) -> None:
                # Importing and initializing the runtime can exceed five seconds
                # on a cold Windows machine. Keep an upper bound for a genuinely
                # wedged child, but do not turn normal cold-start variance into a
                # deterministic failure.
                deadline = time.monotonic() + 30
                last_probe_error: Exception | None = None
                while time.monotonic() < deadline:
                    returncode = process.poll()
                    if returncode is not None:
                        _stdout, stderr = process.communicate(timeout=1)
                        self.fail(
                            "runtime exited before readiness "
                            f"(exit code {returncode}); stderr={stderr[-4000:]!r}"
                        )
                    try:
                        health = get(f"{process_origin}/healthz", timeout=0.2)
                    except Exception as exc:
                        last_probe_error = exc
                        time.sleep(0.02)
                        continue
                    if health.status_code == 200:
                        return
                    time.sleep(0.02)
                if process.poll() is None:
                    process.kill()
                returncode = process.wait(timeout=5)
                _stdout, stderr = process.communicate(timeout=1)
                self.fail(
                    "runtime never became ready "
                    f"(exit code {returncode}); stderr={stderr[-4000:]!r}; "
                    f"last health probe={last_probe_error!r}"
                )

            first = launch()
            try:
                await_ready(first)
                response = get(
                    f"{process_origin}/api/v1/handshake",
                    headers=process_headers,
                    timeout=1,
                )
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(TOKEN, response.text)
                self.assertNotIn(str(database_path), response.text)
                first.kill()
                first.communicate(timeout=5)
                second = launch()
                try:
                    await_ready(second)
                    self.assertEqual(
                        get(
                            f"{process_origin}/api/v1/contracts",
                            headers=process_headers,
                            timeout=1,
                        ).status_code,
                        200,
                    )
                finally:
                    if second.poll() is None:
                        second.kill()
                    second.communicate(timeout=5)
            finally:
                if first.poll() is None:
                    first.kill()
                first.communicate(timeout=5)
                # Windows reports process termination before every inherited
                # SQLite handle is observable as released by filesystem cleanup.
                time.sleep(0.2)


if __name__ == "__main__":
    unittest.main()
