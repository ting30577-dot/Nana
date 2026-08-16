"""D3-09 evidence that product export authority starts at interactive stdin."""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from scripts.run_d3_dev_journey import (
    _open_browser_when_ready,
    create_interactive_runtime,
)


class D309InteractiveLauncherTests(unittest.IsolatedAsyncioTestCase):
    def test_browser_opener_waits_beyond_the_legacy_retry_window(self) -> None:
        attempts = 0

        class ReadyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        def delayed_health(*_args: object, **_kwargs: object) -> ReadyResponse:
            nonlocal attempts
            attempts += 1
            if attempts <= 100:
                raise OSError("runtime still starting")
            return ReadyResponse()

        with (
            patch("scripts.run_d3_dev_journey.urlopen", side_effect=delayed_health),
            patch("scripts.run_d3_dev_journey.webbrowser.open", return_value=True) as opened,
        ):
            result = _open_browser_when_ready(
                "http://127.0.0.1:43130",
                "secret-never-logged",
                threading.Event(),
                retry_interval=0,
            )

        self.assertTrue(result)
        self.assertEqual(attempts, 101)
        opened.assert_called_once_with(
            "http://127.0.0.1:43130/#bootstrap=secret-never-logged"
        )

    def test_browser_opener_reports_when_runtime_stops_before_ready(self) -> None:
        stop_event = threading.Event()
        stop_event.set()
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            result = _open_browser_when_ready(
                "http://127.0.0.1:43130",
                "secret-never-logged",
                stop_event,
                retry_interval=0,
            )

        self.assertFalse(result)
        self.assertIn("stopped before", stderr.getvalue())
        self.assertNotIn("secret-never-logged", stderr.getvalue())

    def test_launcher_creates_workspace_parent_and_reads_empty_target_from_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "nested" / "workspace"
            target = root / "dedicated-export"
            target.mkdir()
            prompts: list[str] = []

            def choose(prompt: str) -> str:
                prompts.append(prompt)
                return str(target)

            app, session, summary = create_interactive_runtime(
                database=workspace / "nana.db",
                port=43130,
                build_root=Path(__file__).resolve().parents[1] / "nana_web" / "dist",
                input_fn=choose,
                bootstrap_secret="b" * 43,
            )
            try:
                self.assertTrue(workspace.is_dir())
                self.assertEqual(len(prompts), 1)
                self.assertIn("existing dedicated empty fixed-local", prompts[0])
                self.assertEqual(summary.provenance, "interactive_user")
                self.assertEqual(summary.label, "Dedicated local draft folder")
                self.assertNotIn(str(target), summary.selection_id)
                self.assertNotIn(str(target), summary.label)
                self.assertEqual(session.origin, "http://127.0.0.1:43130")
                self.assertIsNotNone(app.state.runtime_control.journey.export_selections)
                self.assertTrue(any(route.path == "/api/v1/session/exchange" for route in app.routes))
            finally:
                app.state.runtime_control.journey.export_selections.close()

    async def test_browser_bootstrap_is_one_use_and_never_needs_the_bearer_in_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            target = root / "dedicated-export"
            workspace.mkdir()
            target.mkdir()
            secret = "s" * 43
            app, session, _summary = create_interactive_runtime(
                database=workspace / "nana.db",
                port=43131,
                build_root=Path(__file__).resolve().parents[1] / "nana_web" / "dist",
                input_fn=lambda _prompt: str(target),
                bootstrap_secret=secret,
            )
            try:
                async with app.router.lifespan_context(app):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url=session.origin
                    ) as client:
                        index = await client.get("/", headers={"Host": session.authority})
                        self.assertEqual(index.status_code, 200)
                        exchanged = await client.post(
                            "/api/v1/session/exchange",
                            headers={
                                "Host": session.authority,
                                "Origin": session.origin,
                                "X-Nana-Bootstrap": "1",
                                "Content-Type": "application/json",
                            },
                            json={"bootstrap_secret": secret},
                        )
                        self.assertEqual(exchanged.status_code, 200)
                        authorization = exchanged.json()["authorization"]
                        self.assertTrue(authorization.startswith("Bearer "))
                        set_cookie = exchanged.headers["set-cookie"]
                        self.assertIn("HttpOnly", set_cookie)
                        self.assertIn("SameSite=strict", set_cookie)
                        restored = await client.post(
                            "/api/v1/session/restore",
                            headers={
                                "Host": session.authority,
                                "Origin": session.origin,
                                "X-Nana-Session-Restore": "1",
                                "Content-Type": "application/json",
                            },
                            json={},
                        )
                        self.assertEqual(restored.status_code, 200)
                        self.assertEqual(restored.json()["authorization"], authorization)
                        replay = await client.post(
                            "/api/v1/session/exchange",
                            headers={
                                "Host": session.authority,
                                "Origin": session.origin,
                                "X-Nana-Bootstrap": "1",
                                "Content-Type": "application/json",
                            },
                            json={"bootstrap_secret": secret},
                        )
                        self.assertEqual(replay.status_code, 401)
                        handshake = await client.get(
                            "/api/v1/handshake",
                            headers={
                                "Host": session.authority,
                                "Origin": session.origin,
                                "Authorization": authorization,
                            },
                        )
                        self.assertEqual(handshake.status_code, 200)

                        malicious = await client.post(
                            "/api/v1/session/exchange",
                            headers={
                                "Host": session.authority,
                                "Origin": "http://127.0.0.1:9",
                                "X-Nana-Bootstrap": "1",
                                "Content-Type": "application/json",
                            },
                            json={"bootstrap_secret": secret},
                        )
                        rebound = await client.post(
                            "/api/v1/session/exchange",
                            headers={
                                "Host": "localhost:43131",
                                "Origin": session.origin,
                                "X-Nana-Bootstrap": "1",
                                "Content-Type": "application/json",
                            },
                            json={"bootstrap_secret": secret},
                        )
                        self.assertEqual(malicious.status_code, 403)
                        self.assertEqual(rebound.status_code, 403)
                        client.cookies.clear()
                        rejected_restore = await client.post(
                            "/api/v1/session/restore",
                            headers={
                                "Host": session.authority,
                                "Origin": session.origin,
                                "X-Nana-Session-Restore": "1",
                                "Content-Type": "application/json",
                            },
                            json={},
                        )
                        self.assertEqual(rejected_restore.status_code, 401)
            finally:
                app.state.runtime_control.journey.export_selections.close()

    def test_crashed_owner_releases_lock_and_second_process_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "nana.db"
            ready = root / "ready"
            code = (
                "from pathlib import Path; from nana_sidecar.storage.workspace_lock import WorkspaceRuntime; "
                f"r=WorkspaceRuntime(Path({str(database)!r})); r.start(); "
                f"Path({str(ready)!r}).write_text('ready'); "
                "import time; time.sleep(60)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1]
            )
            try:
                for _ in range(100):
                    if ready.exists():
                        break
                    time.sleep(0.02)
                self.assertTrue(ready.exists())
                process.kill()
                process.wait(timeout=5)
                replacement = __import__(
                    "nana_sidecar.storage.workspace_lock", fromlist=["WorkspaceRuntime"]
                ).WorkspaceRuntime(database)
                replacement.start()
                self.assertEqual(replacement.state, "ready")
                self.assertIsNotNone(replacement.reconciliation_report)
                replacement.close()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
