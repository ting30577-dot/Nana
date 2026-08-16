"""Authenticated runtime evidence for the D3-07 narrow browser surface."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from nana_sidecar.contracts.journey import DraftFindingRequest, StartRunRequest
from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    load_dev_journey,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.export_selection import ExportSelectionRegistry
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.journey_commands import JourneyCommandService
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


TOKEN = "d3-07-runtime-" + "r" * 40
ORIGIN = "http://127.0.0.1:43123"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class D307RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.workspace_root = root / "workspace"
        self.workspace_root.mkdir()
        self.target = root / "export"
        self.target.mkdir()
        self.workspace = WorkspaceRuntime(self.workspace_root / "nana.db")
        self.definition = read_dev_journey_definition()
        self.actor = local_fixture_actor()
        self.session = LocalSession(token=TOKEN, origin=ORIGIN)
        self.selections = ExportSelectionRegistry(
            session=self.session,
            workspace_root=self.workspace_root,
            actor_id=str(self.actor.id),
            allow_test_harness=True,
        )
        self.summary = self.selections.register_test_harness_target(str(self.target))
        self.app = create_runtime_app(
            workspace_runtime=self.workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=self.actor,
                resources=(frozen_resource_descriptor(self.definition),),
                now=_now,
                export_selections=self.selections,
            ),
        )

    async def asyncTearDown(self) -> None:
        self.selections.close()
        if self.workspace.state == "ready":
            await self.app.state.runtime_control.close()
        self.tempdir.cleanup()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Host": "127.0.0.1:43123",
            "Origin": ORIGIN,
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }

    async def _seed_terminal_finding(self) -> str:
        def seed() -> str:
            connection = self.workspace.connection
            assert connection is not None
            service = JourneyCommandService(
                connection,
                actor=self.actor,
                resources=(frozen_resource_descriptor(self.definition),),
                now=_now,
                export_selections=self.selections,
            )
            loaded = load_dev_journey(service, self.definition)
            ids = {key: str(value) for key, value in loaded.ids.items()}
            run = service.execute(
                StartRunRequest(
                    type="StartRun",
                    command_id=uuid4(),
                    expected_revision=1,
                    project_id=ids["project"],
                    inquiry_id=ids["inquiry"],
                    plan_id=ids["plan"],
                    plan_revision=1,
                    random_seed=0,
                )
            )
            run_id = next(key.split(":", 1)[1] for key in run.affected_revisions if key.startswith("run:"))
            finding = service.execute(
                DraftFindingRequest(
                    type="DraftFinding",
                    command_id=uuid4(),
                    expected_revision=1,
                    inquiry_id=ids["inquiry"],
                    statement="The canonical locked result supports the public finding.",
                    confidence_basis="The terminal Run and successful Receipt are canonical.",
                    evidence_ids=(),
                    terminal_run_ids=(run_id,),
                )
            )
            return next(key.split(":", 1)[1] for key in finding.affected_revisions if key.startswith("finding:"))

        return await self.app.state.runtime_control._run_on_writer(seed)

    async def test_handshake_exposes_only_opaque_summary_and_http_journey_exports(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            finding_id = await self._seed_terminal_finding()
            async with AsyncClient(transport=ASGITransport(app=self.app), base_url=ORIGIN) as client:
                handshake = await client.get("/api/v1/handshake", headers=self.headers)
                self.assertEqual(handshake.status_code, 200)
                body = handshake.json()
                self.assertTrue(body["external_effects_enabled"])
                self.assertEqual(
                    body["export_selections"],
                    [{
                        "selection_id": self.summary.selection_id,
                        "label": "Dedicated local draft folder",
                        "expires_at": self.summary.expires_at,
                        "provenance": "test_harness",
                    }],
                )
                self.assertNotIn(str(self.target), handshake.text)

                injected_id = str(uuid4())
                injected = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps({
                        "type": "RequestApproval",
                        "command_id": injected_id,
                        "expected_revision": 1,
                        "finding_id": finding_id,
                        "target_selection_id": self.summary.selection_id,
                        "path": str(self.target),
                    }),
                )
                self.assertEqual(injected.status_code, 422)
                command_count = await self.app.state.runtime_control._run_on_writer(
                    lambda: self.workspace.connection.execute(
                        "SELECT COUNT(*) FROM command_log WHERE command_id = ?",
                        (injected_id,),
                    ).fetchone()[0]
                )
                self.assertEqual(command_count, 0)

                prepared = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps({
                        "type": "RequestApproval",
                        "command_id": str(uuid4()),
                        "expected_revision": 1,
                        "finding_id": finding_id,
                        "target_selection_id": self.summary.selection_id,
                    }),
                )
                self.assertEqual(prepared.status_code, 200, prepared.text)
                keys = prepared.json()["affected_revisions"]
                approval_id = next(key.split(":", 1)[1] for key in keys if key.startswith("approval:"))
                subject_hash = await self.app.state.runtime_control._run_on_writer(
                    lambda: self.workspace.connection.execute(
                        "SELECT subject_hash FROM approvals WHERE id = ?",
                        (approval_id,),
                    ).fetchone()[0]
                )
                decided = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps({
                        "type": "DecideApproval",
                        "command_id": str(uuid4()),
                        "expected_revision": 1,
                        "approval_id": approval_id,
                        "subject_hash": subject_hash,
                        "decision": "approved",
                    }),
                )
                self.assertEqual(decided.status_code, 200, decided.text)
                for _ in range(200):
                    state = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute(
                            "SELECT actions.state FROM actions JOIN approvals ON approvals.subject_id = actions.id WHERE approvals.id = ?",
                            (approval_id,),
                        ).fetchone()[0]
                    )
                    if state in {"succeeded", "failed", "effect_unknown"}:
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(state, "succeeded")
                snapshot = await client.get("/api/v1/bootstrap", headers=self.headers)
                self.assertEqual(snapshot.status_code, 200)
                projection = snapshot.json()
                approval = next(item for item in projection["approvals"] if item["id"] == approval_id)
                self.assertEqual((approval["decision"], approval["consumed"]), ("approved", True))
                export = next(item for item in projection["exports"] if item["approval_id"] == approval_id)
                self.assertEqual((export["state"], export["write_fenced"]), ("succeeded", 1))


if __name__ == "__main__":
    unittest.main()
