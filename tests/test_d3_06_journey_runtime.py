"""D3-06 owner-lane/worker bridge and locked journey tests."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    load_dev_journey,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.read_models import BootstrapReadModel
from nana_sidecar.sse import LocalSession
from nana_sidecar.contracts.common import EffectScope
from nana_sidecar.storage.locked_unittest_executor import LockedProcessResult
from nana_sidecar.storage.artifact_commits import ArtifactReader
from nana_sidecar.storage.artifacts import ArtifactStore
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


ORIGIN = "http://127.0.0.1:43123"
TOKEN = "d3-06-session-" + ("c" * 40)


class D306JourneyRuntimeTests(unittest.IsolatedAsyncioTestCase):
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
                now=lambda: "2026-08-09T00:00:01Z",
            ),
        )

    async def asyncTearDown(self) -> None:
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

    async def _seed(self) -> dict[str, str]:
        def seed() -> dict[str, str]:
            connection = self.workspace.connection
            if connection is None:
                raise RuntimeError("workspace connection unavailable")
            from nana_sidecar.storage.journey_commands import JourneyCommandService

            service = JourneyCommandService(
                connection,
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:01Z",
            )
            loaded = load_dev_journey(service, self.definition)
            return {name: str(value) for name, value in loaded.ids.items()}

        return await self.app.state.runtime_control._run_on_writer(seed)

    def _start_payload(self, ids: dict[str, str], command_id: str) -> dict[str, object]:
        return {
            "type": "StartRun",
            "command_id": command_id,
            "expected_revision": 1,
            "project_id": ids["project"],
            "inquiry_id": ids["inquiry"],
            "plan_id": ids["plan"],
            "plan_revision": 1,
            "random_seed": 0,
        }

    async def test_start_run_uses_worker_and_projects_receipt(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                command_id = str(uuid4())
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(self._start_payload(ids, command_id)),
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "accepted")
                run_id = next(
                    value.split(":", 1)[1]
                    for value in response.json()["affected_revisions"]
                    if value.startswith("run:")
                )
                for _ in range(100):
                    state = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute(
                            "SELECT state FROM runs ORDER BY created_at DESC LIMIT 1"
                        ).fetchone()["state"]
                    )
                    if state == "succeeded":
                        break
                    await asyncio.sleep(0.02)
                self.assertEqual(state, "succeeded")
                facts = await self.app.state.runtime_control._run_on_writer(
                    lambda: (
                        self.workspace.connection.execute(
                            "SELECT COUNT(*) FROM action_receipts"
                        ).fetchone()[0],
                        self.workspace.connection.execute(
                            "SELECT COUNT(*) FROM actions WHERE state = 'succeeded'"
                        ).fetchone()[0],
                    )
                )
                self.assertEqual(facts, (1, 1))

                artifact_facts = await self.app.state.runtime_control._run_on_writer(
                    lambda: self.workspace.connection.execute(
                        "SELECT actions.args_artifact_id, action_receipts.after_artifact_ids_json "
                        "FROM actions JOIN action_receipts ON action_receipts.action_id = actions.id "
                        "WHERE actions.run_id = (SELECT id FROM runs ORDER BY created_at DESC LIMIT 1)"
                    ).fetchone()
                )
                args_artifact_id = str(artifact_facts["args_artifact_id"])
                output_ids = json.loads(str(artifact_facts["after_artifact_ids_json"]))
                self.assertEqual(len(output_ids), 1)
                stored_bytes = await self.app.state.runtime_control._run_on_writer(
                    lambda: (
                        ArtifactReader(
                            self.workspace.connection,
                            ArtifactStore(self.workspace.database_path.parent),
                        ).read_bytes(args_artifact_id),
                        ArtifactReader(
                            self.workspace.connection,
                            ArtifactStore(self.workspace.database_path.parent),
                        ).read_bytes(output_ids[0]),
                    )
                )
                self.assertIn(b"test_id", stored_bytes[0])
                self.assertIn(b"OK", stored_bytes[1])
                provenance = await self.app.state.runtime_control._run_on_writer(
                    lambda: (
                        self.workspace.connection.execute(
                            "SELECT producer_run_id FROM artifacts WHERE id = ?",
                            (output_ids[0],),
                        ).fetchone()[0],
                        self.workspace.connection.execute(
                            "SELECT COUNT(*) FROM relations WHERE type = 'run_produces_artifact' "
                            "AND source_id = ? AND target_id = ? AND producer_run_id = ?",
                            (run_id, output_ids[0], run_id),
                        ).fetchone()[0],
                        self.workspace.connection.execute(
                            "SELECT COUNT(*) FROM events JOIN outbox_events "
                            "ON outbox_events.event_id = events.id "
                            "WHERE events.aggregate_type = 'relation' AND events.run_id = ? "
                            "AND events.action_id IS NOT NULL AND events.type = 'relation.created'",
                            (run_id,),
                        ).fetchone()[0],
                    )
                )
                self.assertEqual(provenance, (run_id, 1, 1))
                gate_rows = await self.app.state.runtime_control._run_on_writer(
                    lambda: self.workspace.connection.execute(
                        "SELECT events.payload_json, events.causation_id FROM events "
                        "JOIN outbox_events ON outbox_events.event_id = events.id "
                        "WHERE events.run_id = ? AND events.type = 'action.output' "
                        "AND json_extract(events.payload_json, '$.phase') = 'gate_decision' "
                        "ORDER BY events.id",
                        (run_id,),
                    ).fetchall()
                )
                gate_payloads = [json.loads(str(row["payload_json"])) for row in gate_rows]
                self.assertEqual(
                    {payload["gate_id"] for payload in gate_payloads},
                    {f"Gate-{letter}" for letter in "ABCDEFGH"},
                )
                self.assertTrue(all(row["causation_id"] == command_id for row in gate_rows))
                self.assertTrue(all(payload["fixture_digest"] for payload in gate_payloads))
                self.assertTrue(all(payload["capability_digest"] for payload in gate_payloads))
                gate_g = next(payload for payload in gate_payloads if payload["gate_id"] == "Gate-G")
                self.assertEqual(gate_g["decision"], "accepted")
                receipt_projection = await self.app.state.runtime_control._run_on_writer(
                    lambda: BootstrapReadModel._receipts(self.workspace.connection)[0]
                )
                self.assertEqual(
                    receipt_projection["billing_basis"],
                    "measured_observed_effect",
                )

    async def test_success_is_durable_after_runtime_close_and_database_reopen(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(self._start_payload(ids, str(uuid4()))),
                )
                self.assertEqual(response.status_code, 200, response.text)
                run_id = next(
                    value.split(":", 1)[1]
                    for value in response.json()["affected_revisions"]
                    if value.startswith("run:")
                )
                for _ in range(100):
                    state = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute(
                            "SELECT state FROM runs WHERE id = ?", (run_id,)
                        ).fetchone()["state"]
                    )
                    if state == "succeeded":
                        break
                    await asyncio.sleep(0.02)
                self.assertEqual(state, "succeeded")

        reopened = WorkspaceRuntime(database_path)
        connection = reopened.start()
        try:
            row = connection.execute(
                "SELECT runs.state AS run_state, actions.state AS action_state, "
                "action_receipts.result, action_receipts.after_artifact_ids_json "
                "FROM runs JOIN actions ON actions.run_id = runs.id "
                "JOIN action_receipts ON action_receipts.action_id = actions.id "
                "WHERE runs.id = ?",
                (run_id,),
            ).fetchone()
            self.assertEqual((row["run_state"], row["action_state"], row["result"]),
                             ("succeeded", "succeeded", "succeeded"))
            output_id = json.loads(str(row["after_artifact_ids_json"]))[0]
            content = ArtifactReader(
                connection, ArtifactStore(database_path.parent)
            ).read_bytes(output_id)
            self.assertIn(b"OK", content)
        finally:
            reopened.close()

    async def test_executor_uses_durable_authorization_after_source_grant_revocation(self) -> None:
        """Admission snapshot, not a later Grant query, authorizes execution."""

        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def authorize_revoke_and_complete() -> tuple[object, ...]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import (
                    JourneyCommandRequest,
                    to_canonical_command,
                )
                from nana_sidecar.storage.journey_commands import JourneyCommandService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                authorization = connection.execute(
                    "SELECT actions.authorization_ref, "
                    "action_authorizations.authorization_source, "
                    "action_authorizations.authorization_ref AS durable_ref "
                    "FROM actions JOIN action_authorizations "
                    "ON action_authorizations.action_id = actions.id "
                    "WHERE actions.id = ?",
                    (context["action_id"],),
                ).fetchone()
                grant_id = str(authorization["authorization_ref"]).removeprefix(
                    "policy_grant:"
                )
                with connection:
                    connection.execute(
                        "UPDATE policy_grants SET state = 'revoked' WHERE id = ?",
                        (grant_id,),
                    )
                self.assertTrue(service.commit_spawn_fence(context))
                service.complete_locked_action(
                    command,
                    context,
                    LockedProcessResult(
                        exit_code=0,
                        stdout=b"OK\n",
                        stderr=b"",
                        wall_clock_ms=1,
                        actual_effects=EffectScope(),
                    ),
                )
                settled = connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result, "
                    "policy_grants.state, "
                    "(SELECT COUNT(*) FROM approvals), "
                    "(SELECT COUNT(*) FROM approval_consumptions) "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "JOIN policy_grants ON policy_grants.id = ? "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (grant_id, context["run_id"], context["action_id"]),
                ).fetchone()
                return (
                    str(authorization["authorization_source"]),
                    str(authorization["durable_ref"]),
                    str(authorization["authorization_ref"]),
                    *tuple(settled),
                )

            facts = await self.app.state.runtime_control._run_on_writer(
                authorize_revoke_and_complete
            )
            self.assertEqual(facts[0], "policy_grant")
            self.assertEqual(facts[1], facts[2])
            self.assertEqual(
                facts[3:],
                ("succeeded", "succeeded", "succeeded", "revoked", 0, 0),
            )

    async def test_start_run_replay_does_not_spawn_second_action(self) -> None:
        command_id = str(uuid4())
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                first = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(self._start_payload(ids, command_id)),
                )
                second = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(self._start_payload(ids, command_id)),
                )
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(second.status_code, 200, second.text)
            self.assertEqual(second.json()["status"], "replayed")
            count = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute(
                    "SELECT COUNT(*) FROM runs"
                ).fetchone()[0]
            )
            self.assertEqual(count, 1)

    async def test_browser_cannot_supply_backend_capability_material(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            payload = self._start_payload(ids, str(uuid4()))
            payload["backend"] = {
                "id": "python.unittest.locked",
                "version": "1",
            }
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(payload),
                )
            self.assertEqual(response.status_code, 422, response.text)
            count = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute(
                    "SELECT COUNT(*) FROM runs"
                ).fetchone()[0]
            )
            self.assertEqual(count, 0)

    async def test_rejected_start_run_does_not_materialize_args_artifact(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            payload = self._start_payload(ids, str(uuid4()))
            payload["expected_revision"] = 2
            before = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute(
                    "SELECT COUNT(*) FROM artifacts"
                ).fetchone()[0]
            )
            async with AsyncClient(
                transport=ASGITransport(app=self.app), base_url=ORIGIN
            ) as client:
                response = await client.post(
                    "/api/v1/journey/commands",
                    headers=self.headers,
                    content=json.dumps(payload),
                )
            self.assertEqual(response.status_code, 409, response.text)
            after = await self.app.state.runtime_control._run_on_writer(
                lambda: self.workspace.connection.execute(
                    "SELECT COUNT(*) FROM artifacts"
                ).fetchone()[0]
            )
            self.assertEqual(after, before)

    async def test_budget_exhaustion_never_spawns_and_settles_action(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def exhaust_and_reconcile() -> tuple[object, ...]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.budget_accounting import BudgetAccountingService
                from nana_sidecar.storage.journey_commands import JourneyCommandService
                from nana_sidecar.storage.locked_unittest_executor import LockedExecutorError

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                run_id = next(
                    key.split(":", 1)[1]
                    for key in result.affected_revisions
                    if key.startswith("run:")
                )
                with connection:
                    BudgetAccountingService(
                        connection,
                        now=lambda: "2026-08-09T00:00:01Z",
                    )._ensure_ledger(run_id)
                    connection.execute(
                        "UPDATE run_budget_ledger SET exhausted = 1, "
                        "exhausted_reason = 'max_actions_exhausted', "
                        "exhausted_at = '2026-08-09T00:00:01Z' WHERE run_id = ?",
                        (run_id,),
                    )
                with self.assertRaises(LockedExecutorError) as captured:
                    service.prepare_locked_action(command, result)
                self.assertEqual(captured.exception.code, "E_ACTION_NOT_CLAIMED")
                service.reconcile_locked_failure(command, result, captured.exception.code)
                return tuple(connection.execute(
                    "SELECT runs.state, actions.state, run_budget_ledger.exhausted, "
                    "run_budget_ledger.started_actions, "
                    "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id) "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN run_budget_ledger ON run_budget_ledger.run_id = runs.id "
                    "WHERE runs.id = ?",
                    (run_id,),
                ).fetchone())

            facts = await self.app.state.runtime_control._run_on_writer(
                exhaust_and_reconcile
            )
            self.assertEqual(facts, ("budget_exceeded", "cancelled", 1, 0, 0))

    async def test_cancel_after_spawn_committed_records_effect_unknown_receipt(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def cancellable_runner(test_id, workspace_root, timeout_seconds, max_output_bytes, cancel_requested):
                while not cancel_requested():
                    time.sleep(0.005)
                return LockedProcessResult(
                    exit_code=None,
                    stdout=b"",
                    stderr=b"",
                    wall_clock_ms=5,
                    cancelled=True,
                    actual_effects=EffectScope(),
                )

            with patch("nana_sidecar.runtime_app.default_locked_unittest_runner", cancellable_runner):
                async with AsyncClient(
                    transport=ASGITransport(app=self.app), base_url=ORIGIN
                ) as client:
                    start = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps(self._start_payload(ids, str(uuid4()))),
                    )
                    self.assertEqual(start.status_code, 200, start.text)
                    run_id = next(
                        value.split(":", 1)[1]
                        for value in start.json()["affected_revisions"]
                        if value.startswith("run:")
                    )
                    action_id = next(
                        value.split(":", 1)[1]
                        for value in start.json()["affected_revisions"]
                        if value.startswith("action:")
                    )
                    for _ in range(100):
                        phase = await self.app.state.runtime_control._run_on_writer(
                            lambda: self.workspace.connection.execute(
                                "SELECT EXISTS(SELECT 1 FROM events "
                                "WHERE aggregate_type = 'action' AND aggregate_id = ? "
                                "AND type = 'action.output' "
                                "AND json_extract(payload_json, '$.phase') = 'spawn_committed')",
                                (action_id,),
                            ).fetchone()[0]
                        )
                        if phase:
                            break
                        await asyncio.sleep(0.01)
                    cancel = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps({
                            "type": "CancelRun",
                            "command_id": str(uuid4()),
                            "expected_revision": 1,
                            "run_id": run_id,
                            "reason": "user stop",
                        }),
                    )
                    self.assertEqual(cancel.status_code, 200, cancel.text)
                for _ in range(100):
                    state = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute(
                            "SELECT state FROM runs WHERE id = ?", (run_id,)
                        ).fetchone()["state"]
                    )
                    if state == "cancelled":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(state, "cancelled")
                facts = await self.app.state.runtime_control._run_on_writer(
                    lambda: self.workspace.connection.execute(
                        "SELECT actions.state, action_receipts.result "
                        "FROM actions JOIN action_receipts ON action_receipts.action_id = actions.id "
                        "WHERE actions.run_id = ?", (run_id,)
                    ).fetchone()
                )
                self.assertEqual(tuple(facts), ("effect_unknown", "effect_unknown"))

                snapshot_and_fence = await self.app.state.runtime_control._run_on_writer(
                    lambda: (
                        json.loads(self.workspace.connection.execute(
                            "SELECT snapshot_json FROM runs WHERE id = ?", (run_id,)
                        ).fetchone()[0]),
                        self.workspace.connection.execute(
                            "SELECT COUNT(*) FROM events JOIN outbox_events ON outbox_events.event_id = events.id "
                            "WHERE events.aggregate_type = 'action' AND events.aggregate_id = ? "
                            "AND events.type = 'action.output' "
                            "AND json_extract(events.payload_json, '$.phase') = 'spawn_committed'",
                            (action_id,),
                        ).fetchone()[0],
                    )
                )
                self.assertNotIn("execution_phase", snapshot_and_fence[0])
                self.assertEqual(snapshot_and_fence[1], 1)

    async def test_pause_resume_controls_worker_and_freezes_run_state(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            observed = {"paused": False, "resumed": False}

            def pausable_runner(test_id, workspace_root, timeout_seconds, max_output_bytes, signals):
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and not signals.pause_requested():
                    time.sleep(0.005)
                observed["paused"] = signals.pause_requested()
                while signals.pause_requested() and not signals():
                    time.sleep(0.005)
                observed["resumed"] = not signals.pause_requested()
                return LockedProcessResult(
                    exit_code=0, stdout=b"ok", stderr=b"", wall_clock_ms=10,
                    actual_effects=EffectScope(),
                )

            with patch("nana_sidecar.runtime_app.default_locked_unittest_runner", pausable_runner):
                async with AsyncClient(
                    transport=ASGITransport(app=self.app), base_url=ORIGIN
                ) as client:
                    start = await client.post(
                        "/api/v1/journey/commands", headers=self.headers,
                        content=json.dumps(self._start_payload(ids, str(uuid4()))),
                    )
                    self.assertEqual(start.status_code, 200, start.text)
                    run_id = next(value.split(":", 1)[1] for value in start.json()["affected_revisions"] if value.startswith("run:"))
                    for _ in range(100):
                        if run_id in self.app.state.runtime_control.locked_pauses:
                            break
                        await asyncio.sleep(0.01)
                    pause = await client.post(
                        "/api/v1/journey/commands", headers=self.headers,
                        content=json.dumps({"type": "PauseRun", "command_id": str(uuid4()), "expected_revision": 1, "run_id": run_id, "reason": "inspect"}),
                    )
                    self.assertEqual(pause.status_code, 200, pause.text)
                    paused_fact = await self.app.state.runtime_control._run_on_writer(
                        lambda: tuple(self.workspace.connection.execute("SELECT state, result_json FROM runs WHERE id = ?", (run_id,)).fetchone())
                    )
                    self.assertEqual(paused_fact[0], "paused", paused_fact)
                    self.assertEqual(json.loads(paused_fact[1])["reason"], "user_paused", paused_fact)
                    stale_cancel = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps({
                            "type": "CancelRun",
                            "command_id": str(uuid4()),
                            "expected_revision": 1,
                            "run_id": run_id,
                            "reason": "stale cancellation",
                        }),
                    )
                    self.assertEqual(stale_cancel.status_code, 409, stale_cancel.text)
                    self.assertEqual(
                        stale_cancel.json()["error"]["details"]["actual_revision"],
                        2,
                    )
                    self.assertFalse(
                        self.app.state.runtime_control.locked_cancellations[run_id].is_set()
                    )
                    resume = await client.post(
                        "/api/v1/journey/commands", headers=self.headers,
                        content=json.dumps({"type": "ResumeRun", "command_id": str(uuid4()), "expected_revision": 2, "run_id": run_id, "reason": "continue"}),
                    )
                    self.assertEqual(resume.status_code, 200, resume.text)
                for _ in range(100):
                    state = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute("SELECT state FROM runs WHERE id = ?", (run_id,)).fetchone()[0]
                    )
                    if state == "succeeded":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(state, "succeeded")
                self.assertEqual(observed, {"paused": True, "resumed": True})
                event_types = await self.app.state.runtime_control._run_on_writer(
                    lambda: tuple(row[0] for row in self.workspace.connection.execute(
                        "SELECT type FROM events WHERE aggregate_type = 'run' AND aggregate_id = ? ORDER BY id", (run_id,)
                    ))
                )
                self.assertIn("run.paused", event_types)
                self.assertGreaterEqual(event_types.count("run.started"), 1)

    async def test_worker_crash_is_reconciled_with_receipt(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            with patch(
                "nana_sidecar.runtime_app.default_locked_unittest_runner",
                side_effect=RuntimeError("simulated worker crash"),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=self.app), base_url=ORIGIN
                ) as client:
                    start = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps(self._start_payload(ids, str(uuid4()))),
                    )
                    self.assertEqual(start.status_code, 200, start.text)
                    run_id = next(
                        value.split(":", 1)[1]
                        for value in start.json()["affected_revisions"]
                        if value.startswith("run:")
                    )
                for _ in range(100):
                    facts = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute(
                            "SELECT runs.state, actions.state, action_receipts.result "
                            "FROM runs JOIN actions ON actions.run_id = runs.id "
                            "LEFT JOIN action_receipts ON action_receipts.action_id = actions.id "
                            "WHERE runs.id = ?", (run_id,)
                        ).fetchone()
                    )
                    if facts[0] == "orphaned":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(tuple(facts), ("orphaned", "effect_unknown", "effect_unknown"))
                audit = await self.app.state.runtime_control._run_on_writer(
                    lambda: (
                        json.loads(str(self.workspace.connection.execute(
                            "SELECT payload_json FROM events "
                            "WHERE run_id = ? AND type = 'action.output' "
                            "AND json_extract(payload_json, '$.gate_id') = 'Gate-G'",
                            (run_id,),
                        ).fetchone()[0])),
                        BootstrapReadModel._receipts(self.workspace.connection)[0],
                    )
                )
                self.assertEqual(audit[0]["decision"], "rejected")
                self.assertEqual(audit[0]["decision_source"], "runner_liveness_not_confirmed")
                self.assertEqual(
                    audit[1]["billing_basis"],
                    "conservative_uncertain_effect",
                )

    async def test_terminal_settlement_failure_rolls_back_action_and_recovers(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def fail_then_reconcile() -> tuple[tuple[object, ...], int, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService
                from nana_sidecar.storage.locked_unittest_executor import LockedUnittestExecutorService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                self.assertTrue(service.commit_spawn_fence(context))
                process = LockedProcessResult(
                    exit_code=0,
                    stdout=b"OK\n",
                    stderr=b"",
                    wall_clock_ms=1,
                    actual_effects=EffectScope(),
                )
                with patch.object(
                    LockedUnittestExecutorService,
                    "_settle_terminal_run_after_process",
                    side_effect=RuntimeError("injected post-action failure"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "post-action failure"):
                        service.complete_locked_action(command, context, process)
                rolled_back = connection.execute(
                    "SELECT runs.state, actions.state, "
                    "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id), "
                    "(SELECT COUNT(*) FROM events WHERE aggregate_type = 'action' "
                    "AND aggregate_id = actions.id "
                    "AND type IN ('action.completed', 'action.cancelled', 'action.effect_unknown')), "
                    "(SELECT COUNT(*) FROM events WHERE aggregate_type = 'action' "
                    "AND aggregate_id = actions.id AND type = 'action.output' "
                    "AND json_extract(payload_json, '$.phase') = 'gate_decision'), "
                    "(SELECT COUNT(*) FROM artifacts WHERE state = 'available' "
                    "AND json_extract(retention_json, '$.kind') = 'd3_locked_test_result'), "
                    "(SELECT COUNT(*) FROM artifacts WHERE state = 'staged' "
                    "AND json_extract(retention_json, '$.kind') = 'd3_locked_test_result'), "
                    "(SELECT COUNT(*) FROM relations WHERE producer_run_id = runs.id), "
                    "(SELECT COUNT(*) FROM artifacts WHERE producer_run_id = runs.id) "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                reconciled = service.reconcile_stale_locked_runs()
                recovered = connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result, "
                    "(SELECT COUNT(*) FROM artifacts WHERE state = 'available' "
                    "AND producer_run_id = runs.id) "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                return tuple(rolled_back), reconciled, tuple(recovered)

            rolled_back, reconciled, recovered = (
                await self.app.state.runtime_control._run_on_writer(fail_then_reconcile)
            )
            self.assertEqual(
                rolled_back,
                ("running", "running", 0, 0, 0, 0, 0, 0, 0),
            )
            self.assertEqual(reconciled, 1)
            self.assertEqual(
                recovered,
                ("orphaned", "effect_unknown", "effect_unknown", 1),
            )

    async def test_promoted_result_rollback_reopens_without_phantom_receipt_or_double_billing(
        self,
    ) -> None:
        """A promoted orphan blob cannot fabricate terminal SQLite facts."""

        import hashlib

        database_path = self.workspace.database_path
        output_hash = f"sha256:{hashlib.sha256(b'OK\n').hexdigest()}"
        output_path = ArtifactStore(database_path.parent).blob_path(output_hash)
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def promote_then_rollback() -> tuple[str, str, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import (
                    JourneyCommandRequest,
                    to_canonical_command,
                )
                from nana_sidecar.storage.journey_commands import JourneyCommandService
                from nana_sidecar.storage.locked_unittest_executor import (
                    LockedUnittestExecutorService,
                )

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                self.assertTrue(service.commit_spawn_fence(context))
                with patch.object(
                    LockedUnittestExecutorService,
                    "_settle_terminal_run_after_process",
                    side_effect=RuntimeError("injected after result promotion"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "after result promotion"):
                        service.complete_locked_action(
                            command,
                            context,
                            LockedProcessResult(
                                exit_code=0,
                                stdout=b"OK\n",
                                stderr=b"",
                                wall_clock_ms=1,
                                actual_effects=EffectScope(),
                            ),
                        )
                self.assertTrue(output_path.is_file())
                before_restart = connection.execute(
                    "SELECT runs.state, actions.state, "
                    "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id), "
                    "(SELECT COUNT(*) FROM artifacts WHERE producer_run_id = runs.id), "
                    "run_budget_ledger.running_actions, "
                    "json_extract(run_budget_ledger.usage_json, '$.wall_clock_ms') "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN run_budget_ledger ON run_budget_ledger.run_id = runs.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                return (
                    str(context["run_id"]),
                    str(context["action_id"]),
                    tuple(before_restart),
                )

            run_id, action_id, before_restart = (
                await self.app.state.runtime_control._run_on_writer(
                    promote_then_rollback
                )
            )
            self.assertEqual(before_restart, ("running", "running", 0, 0, 1, 0))

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            recovered = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result, "
                    "action_receipts.after_artifact_ids_json, "
                    "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id), "
                    "(SELECT COUNT(*) FROM relations WHERE producer_run_id = runs.id "
                    "AND type = 'run_produces_artifact'), "
                    "run_budget_ledger.running_actions, "
                    "json_extract(run_budget_ledger.usage_json, '$.wall_clock_ms') "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "JOIN run_budget_ledger ON run_budget_ledger.run_id = runs.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            output_ids = json.loads(str(recovered[3]))
            self.assertEqual(
                tuple(recovered[:3]),
                ("orphaned", "effect_unknown", "effect_unknown"),
            )
            self.assertEqual(tuple(recovered[4:]), (1, 1, 0, 0))
            self.assertEqual(len(output_ids), 1)
            output = await restarted_app.state.runtime_control._run_on_writer(
                lambda: ArtifactReader(
                    restarted_workspace.connection,
                    ArtifactStore(database_path.parent),
                ).read_bytes(output_ids[0])
            )
            self.assertIn(b"runner_error", output)

    async def test_restart_repairs_historical_terminal_action_running_run_window(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def leave_historical_window() -> tuple[str, str, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService
                from nana_sidecar.storage.locked_unittest_executor import LockedUnittestExecutorService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                self.assertTrue(service.commit_spawn_fence(context))
                process = LockedProcessResult(
                    exit_code=0,
                    stdout=b"OK\n",
                    stderr=b"",
                    wall_clock_ms=1,
                    actual_effects=EffectScope(),
                )
                with patch.object(
                    LockedUnittestExecutorService,
                    "_settle_terminal_run_after_process",
                    return_value=None,
                ):
                    service.complete_locked_action(command, context, process)
                historical = connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                return str(context["run_id"]), str(context["action_id"]), tuple(historical)

            run_id, action_id, historical = await self.app.state.runtime_control._run_on_writer(
                leave_historical_window
            )
            self.assertEqual(historical, ("running", "succeeded", "succeeded"))

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            repaired = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result, "
                    "(SELECT COUNT(*) FROM events JOIN outbox_events "
                    "ON outbox_events.event_id = events.id "
                    "WHERE events.aggregate_type = 'run' AND events.aggregate_id = runs.id "
                    "AND events.type = 'run.succeeded') "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            self.assertEqual(tuple(repaired), ("succeeded", "succeeded", "succeeded", 1))

    async def test_restart_does_not_downgrade_historical_runner_error_to_cancelled(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def leave_runner_error_window() -> tuple[str, str, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService
                from nana_sidecar.storage.locked_unittest_executor import LockedUnittestExecutorService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                self.assertTrue(service.commit_spawn_fence(context))
                cancel_request = TypeAdapter(JourneyCommandRequest).validate_python({
                    "type": "CancelRun",
                    "command_id": str(uuid4()),
                    "expected_revision": 1,
                    "run_id": context["run_id"],
                    "reason": "cancel intent before historical crash window",
                })
                service.execute(cancel_request)
                with patch.object(
                    LockedUnittestExecutorService,
                    "_settle_terminal_run_after_process",
                    return_value=None,
                ):
                    service.complete_locked_action(
                        command,
                        context,
                        LockedProcessResult(
                            exit_code=None,
                            stdout=b"",
                            stderr=b"",
                            wall_clock_ms=1,
                            runner_error=True,
                            actual_effects=EffectScope(),
                        ),
                    )
                historical = connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                return str(context["run_id"]), str(context["action_id"]), tuple(historical)

            run_id, action_id, historical = await self.app.state.runtime_control._run_on_writer(
                leave_runner_error_window
            )
            self.assertEqual(historical, ("paused", "effect_unknown", "effect_unknown"))

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            repaired = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            self.assertEqual(
                tuple(repaired),
                ("orphaned", "effect_unknown", "effect_unknown"),
            )

    async def test_restart_settles_claimed_action_without_spawn_fence_as_cancelled(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def leave_claimed_without_fence() -> tuple[str, str, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                claimed = connection.execute(
                    "SELECT runs.state, actions.state FROM runs "
                    "JOIN actions ON actions.run_id = runs.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                return str(context["run_id"]), str(context["action_id"]), tuple(claimed)

            run_id, action_id, claimed = await self.app.state.runtime_control._run_on_writer(
                leave_claimed_without_fence
            )
            self.assertEqual(claimed, ("running", "running"))

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            recovered = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result, "
                    "run_budget_ledger.running_actions "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "JOIN run_budget_ledger ON run_budget_ledger.run_id = runs.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            self.assertEqual(
                tuple(recovered),
                ("cancelled", "cancelled", "cancelled", 0),
            )

    async def test_restart_cancels_authorized_unclaimed_action_without_reclaim(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def leave_authorized_unclaimed() -> tuple[str, str, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService
                from nana_sidecar.storage.run_scheduler import RunSchedulerService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                with patch.object(
                    RunSchedulerService,
                    "claim_action",
                    side_effect=RuntimeError("injected before scheduler claim"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "before scheduler claim"):
                        service.prepare_locked_action(command, result)
                run_id = next(
                    key.split(":", 1)[1]
                    for key in result.affected_revisions
                    if key.startswith("run:")
                )
                action_id = next(
                    key.split(":", 1)[1]
                    for key in result.affected_revisions
                    if key.startswith("action:")
                )
                pending = connection.execute(
                    "SELECT runs.state, actions.state, policy_grants.uses "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN policy_grants ON actions.authorization_ref = 'policy_grant:' || policy_grants.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
                return run_id, action_id, tuple(pending)

            run_id, action_id, pending = await self.app.state.runtime_control._run_on_writer(
                leave_authorized_unclaimed
            )
            self.assertEqual(pending, ("running", "authorized", 1))

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            recovered = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, policy_grants.uses, "
                    "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id) "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN policy_grants ON actions.authorization_ref = 'policy_grant:' || policy_grants.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            self.assertEqual(tuple(recovered), ("cancelled", "cancelled", 1, 0))

    async def test_restart_reconciles_persisted_spawn_fence_without_snapshot_mutation(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def leave_spawn_committed() -> tuple[str, str, dict[str, object]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                self.assertTrue(service.commit_spawn_fence(context))
                snapshot = json.loads(connection.execute(
                    "SELECT snapshot_json FROM runs WHERE id = ?",
                    (context["run_id"],),
                ).fetchone()[0])
                return str(context["run_id"]), str(context["action_id"]), snapshot

            run_id, action_id, snapshot = await self.app.state.runtime_control._run_on_writer(
                leave_spawn_committed
            )
            self.assertNotIn("execution_phase", snapshot)

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            facts = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result, "
                    "action_receipts.after_artifact_ids_json "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            self.assertEqual(tuple(facts)[:3],
                             ("orphaned", "effect_unknown", "effect_unknown"))
            self.assertEqual(len(json.loads(str(facts[3]))), 1)

    async def test_restart_orphans_cancel_pending_spawned_action(self) -> None:
        database_path = self.workspace.database_path
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def leave_cancel_pending() -> tuple[str, str, tuple[object, ...]]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                start_request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(start_request, defer_locked_execution=True)
                command = to_canonical_command(start_request, actor=local_fixture_actor())
                context = service.prepare_locked_action(command, result)
                self.assertTrue(service.commit_spawn_fence(context))
                cancel_request = TypeAdapter(JourneyCommandRequest).validate_python({
                    "type": "CancelRun",
                    "command_id": str(uuid4()),
                    "expected_revision": 1,
                    "run_id": context["run_id"],
                    "reason": "persisted cancel before runtime crash",
                })
                service.execute(cancel_request)
                pending = connection.execute(
                    "SELECT runs.state, actions.state FROM runs "
                    "JOIN actions ON actions.run_id = runs.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (context["run_id"], context["action_id"]),
                ).fetchone()
                return str(context["run_id"]), str(context["action_id"]), tuple(pending)

            run_id, action_id, pending = await self.app.state.runtime_control._run_on_writer(
                leave_cancel_pending
            )
            self.assertEqual(pending, ("paused", "running"))

        restarted_workspace = WorkspaceRuntime(database_path)
        restarted_app = create_runtime_app(
            workspace_runtime=restarted_workspace,
            local_session=self.session,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(self.definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(self.definition),),
                now=lambda: "2026-08-09T00:00:02Z",
            ),
        )
        async with restarted_app.router.lifespan_context(restarted_app):
            recovered = await restarted_app.state.runtime_control._run_on_writer(
                lambda: restarted_workspace.connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = ? AND actions.id = ?",
                    (run_id, action_id),
                ).fetchone()
            )
            self.assertEqual(
                tuple(recovered),
                ("orphaned", "effect_unknown", "effect_unknown"),
            )

    async def test_spawn_fence_loss_settles_pre_spawn_cancel_without_worker(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()
            with patch(
                "nana_sidecar.storage.journey_commands.JourneyCommandService.commit_spawn_fence",
                return_value=False,
            ), patch(
                "nana_sidecar.runtime_app.default_locked_unittest_runner",
                side_effect=AssertionError("worker must not spawn after fence loss"),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=self.app), base_url=ORIGIN
                ) as client:
                    start = await client.post(
                        "/api/v1/journey/commands",
                        headers=self.headers,
                        content=json.dumps(self._start_payload(ids, str(uuid4()))),
                    )
                    self.assertEqual(start.status_code, 200, start.text)
                    run_id = next(
                        value.split(":", 1)[1]
                        for value in start.json()["affected_revisions"]
                        if value.startswith("run:")
                    )
                for _ in range(100):
                    facts = await self.app.state.runtime_control._run_on_writer(
                        lambda: self.workspace.connection.execute(
                            "SELECT runs.state, actions.state, action_receipts.result "
                            "FROM runs JOIN actions ON actions.run_id = runs.id "
                            "LEFT JOIN action_receipts ON action_receipts.action_id = actions.id "
                            "WHERE runs.id = ?", (run_id,)
                        ).fetchone()
                    )
                    if facts[0] == "cancelled":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(tuple(facts), ("cancelled", "cancelled", "cancelled"))

    async def test_lost_owner_context_before_spawn_uses_pre_spawn_completion(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            ids = await self._seed()

            def claim_then_reconcile() -> tuple[str, str, str]:
                from pydantic import TypeAdapter

                from nana_sidecar.contracts.journey import JourneyCommandRequest, to_canonical_command
                from nana_sidecar.storage.journey_commands import JourneyCommandService

                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("workspace connection unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=local_fixture_actor(),
                    resources=(frozen_resource_descriptor(self.definition),),
                    now=lambda: "2026-08-09T00:00:01Z",
                )
                request = TypeAdapter(JourneyCommandRequest).validate_python(
                    self._start_payload(ids, str(uuid4()))
                )
                result = service.execute(request, defer_locked_execution=True)
                command = to_canonical_command(request, actor=local_fixture_actor())
                service.prepare_locked_action(command, result)
                service.reconcile_locked_failure(command, result, "simulated_lost_context")
                row = connection.execute(
                    "SELECT runs.state, actions.state, action_receipts.result "
                    "FROM runs JOIN actions ON actions.run_id = runs.id "
                    "LEFT JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE runs.id = (SELECT id FROM runs ORDER BY created_at DESC LIMIT 1)"
                ).fetchone()
                return tuple(row)

            facts = await self.app.state.runtime_control._run_on_writer(claim_then_reconcile)
            self.assertEqual(facts, ("cancelled", "cancelled", "cancelled"))


if __name__ == "__main__":
    unittest.main()
