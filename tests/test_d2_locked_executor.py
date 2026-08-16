"""D2-04 locked unittest executor tests."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from nana_sidecar.contracts.authorization import canonical_json_hash, compute_action_hash
from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_CAPABILITY,
    PYTHON_UNITTEST_LOCKED_TEST_IDS,
    python_unittest_locked_registry_entry,
)
from nana_sidecar.contracts.common import (
    ActorKind,
    ActorRef,
    BudgetSnapshot,
    DataClass,
    EffectScope,
    RiskTier,
)
from nana_sidecar.contracts.domain import CapabilityConstraints, PolicyGrant, PolicyGrantState
from nana_sidecar.contracts.domain import Approval, ApprovalDecision
from nana_sidecar.storage import (
    LockedExecutorError,
    LockedProcessResult,
    LockedUnittestExecutorService,
    RunSchedulerService,
    connect_database,
    initialize_database,
)


NOW_TEXT = "2026-07-31T00:00:00Z"
NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]

WORKSPACE_ID = UUID("20000000-0000-0000-0000-000000000001")
PROJECT_ID = UUID("20000000-0000-0000-0000-000000000002")
INQUIRY_ID = UUID("20000000-0000-0000-0000-000000000003")
PLAN_ID = UUID("20000000-0000-0000-0000-000000000004")
RUN_ID = UUID("20000000-0000-0000-0000-000000000005")
ACTION_ID = UUID("20000000-0000-0000-0000-000000000006")
ARGS_ARTIFACT_ID = UUID("20000000-0000-0000-0000-000000000007")
GRANT_ID = UUID("20000000-0000-0000-0000-000000000008")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _budget() -> BudgetSnapshot:
    return BudgetSnapshot(
        wall_clock_seconds=60,
        cpu_seconds=None,
        memory_bytes=None,
        gpu_seconds=None,
        max_actions=1,
        max_concurrency=1,
        max_model_calls=0,
        max_model_tokens=0,
        max_cost_micros=0,
        max_retries=0,
        max_output_bytes=4096,
        max_artifact_bytes=4096,
        max_download_bytes=0,
        network_targets=(),
        read_roots=("project:source", "project:tests"),
        write_roots=("project:scratch",),
    )


def _material() -> dict[str, object]:
    args = {"test_id": PYTHON_UNITTEST_LOCKED_TEST_IDS[0]}
    return {
        "args": args,
        "args_hash": canonical_json_hash(args),
        "requested_effects": EffectScope(
            reads=("project:source", "project:tests"),
            processes=("builtin:python.unittest.locked",),
        ),
        "budget": _budget(),
    }


class D2LockedExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace_root = ROOT
        self.path = Path(self.tempdir.name) / "nana-vnext.db"
        self.connection = initialize_database(self.path)
        self.actor = ActorRef(kind=ActorKind.SYSTEM, id="d2-executor-test")
        self.material = _material()
        self.args_bytes = _json(self.material["args"]).encode("utf-8")
        self.service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _seed(
        self,
        *,
        state: str = "authorized",
        authorization_ref: str | None = None,
    ) -> None:
        authorization_ref = authorization_ref or f"policy_grant:{GRANT_ID}"
        entry = python_unittest_locked_registry_entry()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO workspaces (
                    id, schema_version, data_root, policy_json, status,
                    revision, created_at
                ) VALUES (?, 4, ?, '{}', 'active', 1, ?)
                """,
                (str(WORKSPACE_ID), "workspace-root", NOW_TEXT),
            )
            self.connection.execute(
                """
                INSERT INTO projects (
                    id, workspace_id, title, status, data_class, revision,
                    created_at
                ) VALUES (?, ?, 'Locked executor', 'active', 'public', 1, ?)
                """,
                (str(PROJECT_ID), str(WORKSPACE_ID), NOW_TEXT),
            )
            self.connection.execute(
                """
                INSERT INTO inquiries (
                    id, project_id, question, acceptance, status, revision,
                    created_at
                ) VALUES (?, ?, 'Question', 'Acceptance', 'active', 1, ?)
                """,
                (str(INQUIRY_ID), str(PROJECT_ID), NOW_TEXT),
            )
            self.connection.execute(
                """
                INSERT INTO plans (
                    id, inquiry_id, revision, status, steps_json, policy_json,
                    budget_json, created_at
                ) VALUES (?, ?, 1, 'approved', ?, '{}', ?, ?)
                """,
                (
                    str(PLAN_ID),
                    str(INQUIRY_ID),
                    _json([{"id": "step-1", "title": "Run frozen unittest"}]),
                    _json(_budget().model_dump(mode="json")),
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO runs (
                    id, project_id, inquiry_id, state, snapshot_json, created_at
                ) VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (
                    str(RUN_ID),
                    str(PROJECT_ID),
                    str(INQUIRY_ID),
                    _json({"budget": _budget().model_dump(mode="json")}),
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO artifacts (
                    id, media_type, blob_hash, size, state, retention_json,
                    created_at
                ) VALUES (?, 'application/json', ?, ?, 'available', '{}', ?)
                """,
                (
                    str(ARGS_ARTIFACT_ID),
                    f"sha256:{hashlib.sha256(self.args_bytes).hexdigest()}",
                    len(self.args_bytes),
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO capability_registry_entries (
                    capability_id, capability_version, executable_digest,
                    entry_json, contract_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.capability.id,
                    entry.capability.version,
                    entry.capability.digest,
                    entry.model_dump_json(),
                    entry.contract_digest,
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO actions (
                    id, run_id, plan_step_id, capability_id,
                    capability_version, executable_digest, args_artifact_id,
                    args_hash, action_hash, risk_tier, requested_effects_json,
                    policy_decision, authorization_ref, state
                ) VALUES (?, ?, 'step-1', ?, ?, ?, ?, ?, ?, ?, ?, 'grant', ?, ?)
                """,
                (
                    str(ACTION_ID),
                    str(RUN_ID),
                    entry.capability.id,
                    entry.capability.version,
                    entry.capability.digest,
                    str(ARGS_ARTIFACT_ID),
                    self.material["args_hash"],
                    compute_action_hash(
                        self._action_material()
                    ),
                    "T2",
                    _json(self.material["requested_effects"].model_dump(mode="json")),
                    authorization_ref,
                    state,
                ),
            )
            authorization_event = self.connection.execute(
                """
                INSERT INTO events (
                    aggregate_type, aggregate_id, aggregate_version,
                    run_id, run_seq, action_id, actor_json, type,
                    payload_json, occurred_at
                ) VALUES ('action', ?, 1, ?, 1, ?, ?, 'action.authorized', ?, ?)
                """,
                (
                    str(ACTION_ID),
                    str(RUN_ID),
                    str(ACTION_ID),
                    _json(self.actor.model_dump(mode="json")),
                    _json({"action_id": str(ACTION_ID), "state": "authorized"}),
                    NOW_TEXT,
                ),
            )
            authorization_event_id = int(authorization_event.lastrowid)
            self.connection.execute(
                "INSERT INTO outbox_events(event_id) VALUES (?)",
                (authorization_event_id,),
            )
            self.connection.execute(
                """
                INSERT INTO action_authorizations (
                    action_id, action_hash, material_json,
                    registry_contract_digest, authorization_source,
                    authorization_ref, authorization_event_id, authorized_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(ACTION_ID),
                    compute_action_hash(self._action_material()),
                    self._action_material().model_dump_json(),
                    entry.contract_digest,
                    "approval" if authorization_ref.startswith("approval:") else "policy_grant",
                    authorization_ref,
                    authorization_event_id,
                    NOW_TEXT,
                ),
            )
            grant = self._grant(entry)
            self.connection.execute(
                """
                INSERT INTO policy_grants (
                    id, project_id, capability_id, capability_version,
                    executable_digest, constraints_json, state, uses,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(grant.id),
                    str(grant.project_id),
                    grant.capability.id,
                    grant.capability.version,
                    grant.capability.digest,
                    _json(grant.constraints.model_dump(mode="json")),
                    grant.state.value,
                    grant.uses,
                    NOW_TEXT,
                ),
            )

    def _action_material(self):
        from nana_sidecar.contracts.authorization import ActionHashMaterial

        return ActionHashMaterial(
            capability=PYTHON_UNITTEST_LOCKED_CAPABILITY,
            args=self.material["args"],
            args_hash=self.material["args_hash"],
            data_class=DataClass.PUBLIC,
            provider=None,
            requested_effects=self.material["requested_effects"],
            network_methods=(),
            budget=self.material["budget"],
            risk_tier=RiskTier.T2,
            reversible=True,
        )

    def _grant(self, entry):
        return PolicyGrant(
            id=GRANT_ID,
            project_id=PROJECT_ID,
            capability=entry.capability,
            constraints=CapabilityConstraints(
                args_schema=entry.args_schema,
                allowed_data_classes=(DataClass.PUBLIC,),
                allowed_providers=(),
                read_roots=("project:source", "project:tests"),
                write_roots=("project:scratch",),
                network_targets=(),
                network_methods=(),
                process_targets=("builtin:python.unittest.locked",),
                per_action_budget=_budget(),
                cumulative_budget=_budget(),
                max_concurrency=1,
                max_uses=2,
                valid_from=NOW - timedelta(minutes=1),
                expires_at=NOW + timedelta(minutes=5),
            ),
            state=PolicyGrantState.ACTIVE,
            uses=0,
            created_at=NOW,
        )

    def _approval(self):
        from uuid import UUID

        return Approval(
            id=UUID("20000000-0000-0000-0000-000000000009"),
            subject_type="action",
            subject_id=ACTION_ID,
            subject_hash=compute_action_hash(self._action_material()),
            capability=PYTHON_UNITTEST_LOCKED_CAPABILITY,
            parameter_summary={"test_id": PYTHON_UNITTEST_LOCKED_TEST_IDS[0]},
            requested_effects=self.material["requested_effects"],
            data_class=DataClass.PUBLIC,
            provider=None,
            budget=self.material["budget"],
            risk_tier=RiskTier.T2,
            reversible=True,
            allowed_uses=1,
            expires_at=NOW + timedelta(minutes=5),
            decision=ApprovalDecision.APPROVED,
            decided_by=ActorRef(kind=ActorKind.USER, id="owner"),
            decided_at=NOW,
        )

    def _receipt(self):
        return self.connection.execute(
            """
            SELECT action_id, action_hash, authorization_source,
                   authorization_ref, approved_by_json, approved_at,
                   result, exit_code, resource_usage_json, actual_effects_json,
                   authorized_effects_json, effect_violation
            FROM action_receipts
            WHERE action_id = ?
            """,
            (str(ACTION_ID),),
        ).fetchone()

    def test_real_locked_unittest_succeeds_without_shell_or_env(self) -> None:
        self._seed()
        result = self.service.execute(
            run_id=str(RUN_ID),
            action_id=str(ACTION_ID),
            actor=self.actor,
        )
        self.assertEqual(result.result, "succeeded")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?",
                (str(ACTION_ID),),
            ).fetchone()["state"],
            "succeeded",
        )
        receipt = self._receipt()
        self.assertEqual(receipt["authorization_source"], "policy_grant")
        self.assertEqual(receipt["result"], "succeeded")
        self.assertEqual(int(receipt["effect_violation"]), 0)
        actual_effects = EffectScope.model_validate_json(receipt["actual_effects_json"])
        self.assertEqual(
            actual_effects,
            EffectScope(
                reads=("project:source", "project:tests"),
                processes=("builtin:python.unittest.locked",),
            ),
        )
        self.assertIn(
            int(json.loads(receipt["resource_usage_json"])["output_bytes"]),
            range(0, 4096),
        )

    def test_cancelled_action_never_reaches_runner(self) -> None:
        called = {"value": False}

        def runner(*args, **kwargs):
            called["value"] = True
            raise AssertionError("runner should not have been called")

        self._seed(state="cancelled")
        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
        )
        with self.assertRaises(LockedExecutorError) as captured:
            service.execute(
                run_id=str(RUN_ID),
                action_id=str(ACTION_ID),
                actor=self.actor,
            )
        self.assertEqual(captured.exception.code, "E_ACTION_NOT_AUTHORIZED")
        self.assertFalse(called["value"])

    def test_cancel_after_claim_before_process_start_never_reaches_runner(self) -> None:
        called = {"value": False}

        def runner(*args, **kwargs):
            called["value"] = True
            raise AssertionError("runner should not have been called")

        def cancel_after_claim() -> None:
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE actions
                    SET state = 'effect_unknown', finished_at = ?
                    WHERE id = ?
                    """,
                    (NOW_TEXT, str(ACTION_ID)),
                )

        self._seed()
        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
            before_process_start=cancel_after_claim,
        )
        with self.assertRaises(LockedExecutorError) as captured:
            service.execute(
                run_id=str(RUN_ID),
                action_id=str(ACTION_ID),
                actor=self.actor,
            )
        self.assertEqual(captured.exception.code, "E_ACTION_CANCEL_RACE")
        self.assertFalse(called["value"])

    def test_timeout_and_output_cap_results_are_audited(self) -> None:
        self._seed()

        def timeout_runner(*args, **kwargs):
            return LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=2000,
                timed_out=True,
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=timeout_runner,
        )
        timeout_result = service.execute(
            run_id=str(RUN_ID),
            action_id=str(ACTION_ID),
            actor=self.actor,
        )
        self.assertEqual(timeout_result.result, "timed_out")
        receipt = self._receipt()
        self.assertEqual(receipt["result"], "timed_out")
        self.assertEqual(int(receipt["effect_violation"]), 0)

    def test_output_cap_triggers_effect_unknown_and_truncation_audit(self) -> None:
        self._seed()

        def truncated_runner(*args, **kwargs):
            return LockedProcessResult(
                exit_code=0,
                stdout=b"x" * 1024,
                stderr=b"y" * 1024,
                wall_clock_ms=100,
                output_truncated=True,
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=truncated_runner,
        )
        result = service.execute(
            run_id=str(RUN_ID),
            action_id=str(ACTION_ID),
            actor=self.actor,
        )
        self.assertEqual(result.result, "effect_unknown")
        receipt = self._receipt()
        self.assertEqual(receipt["result"], "effect_unknown")
        self.assertEqual(int(receipt["effect_violation"]), 0)

    def test_approval_authorization_writes_provenance_into_receipt(self) -> None:
        approval = self._approval()
        self._seed(authorization_ref=f"approval:{approval.id}")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO approvals (
                    id, subject_type, subject_id, subject_hash,
                    capability_json, parameter_summary_json,
                    requested_effects_json, data_class, provider,
                    budget_json, risk_tier, reversible, allowed_uses,
                    expires_at, decision, decided_by_json, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(approval.id),
                    approval.subject_type,
                    str(approval.subject_id),
                    approval.subject_hash,
                    _json(approval.capability.model_dump(mode="json")),
                    _json(approval.parameter_summary),
                    _json(approval.requested_effects.model_dump(mode="json")),
                    approval.data_class.value,
                    approval.provider,
                    _json(approval.budget.model_dump(mode="json")),
                    approval.risk_tier.value,
                    1 if approval.reversible else 0,
                    approval.allowed_uses,
                    NOW_TEXT.replace("00:00:00", "00:05:00"),
                    approval.decision.value,
                    _json(approval.decided_by.model_dump(mode="json")),
                    NOW_TEXT,
                ),
            )

        result = self.service.execute(
            run_id=str(RUN_ID),
            action_id=str(ACTION_ID),
            actor=self.actor,
        )
        self.assertEqual(result.result, "succeeded")
        receipt = self._receipt()
        self.assertEqual(receipt["authorization_source"], "approval")
        self.assertIsNotNone(receipt["approved_by_json"])
        self.assertIsNotNone(receipt["approved_at"])

    def test_crash_and_oversized_output_are_audited(self) -> None:
        self._seed()

        def crash_runner(*args, **kwargs):
            return LockedProcessResult(
                exit_code=1,
                stdout=b"boom",
                stderr=b"",
                wall_clock_ms=50,
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=crash_runner,
        )
        crash_result = service.execute(
            run_id=str(RUN_ID),
            action_id=str(ACTION_ID),
            actor=self.actor,
        )
        self.assertEqual(crash_result.result, "failed")
        receipt = self._receipt()
        self.assertEqual(receipt["result"], "failed")

    def test_authorized_timeout_and_output_budget_reach_runner(self) -> None:
        self.material["budget"] = _budget().model_copy(
            update={"wall_clock_seconds": 7, "max_output_bytes": 123}
        )
        self._seed()
        captured: dict[str, object] = {}

        def runner(test_id, workspace_root, timeout_seconds, max_output_bytes, cancel):
            captured.update(
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
            return LockedProcessResult(
                exit_code=0,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=1,
                actual_effects=self.material["requested_effects"],
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
        )
        self.assertEqual(
            service.execute(
                run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
            ).result,
            "succeeded",
        )
        self.assertEqual(captured, {"timeout_seconds": 7, "max_output_bytes": 123})

    def test_oversized_args_artifact_is_rejected_before_claim(self) -> None:
        self._seed()
        self.args_bytes = json.dumps(
            {
                "test_id": PYTHON_UNITTEST_LOCKED_TEST_IDS[0],
                "padding": "x" * 5000,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        with self.connection:
            self.connection.execute(
                "UPDATE artifacts SET blob_hash = ?, size = ? WHERE id = ?",
                (
                    "sha256:" + hashlib.sha256(self.args_bytes).hexdigest(),
                    len(self.args_bytes),
                    str(ARGS_ARTIFACT_ID),
                ),
            )

        with self.assertRaises(LockedExecutorError) as captured:
            self.service.execute(
                run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
            )

        self.assertEqual(captured.exception.code, "E_ARGS_ARTIFACT_BUDGET")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?", (str(ACTION_ID),)
            ).fetchone()["state"],
            "authorized",
        )

    def test_runner_exception_is_settled_with_receipt_and_budget_release(self) -> None:
        self._seed()

        def runner(*args, **kwargs):
            raise RuntimeError("injected runner failure")

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
        )
        result = service.execute(
            run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
        )
        self.assertEqual(result.result, "effect_unknown")
        self.assertEqual(self._receipt()["result"], "effect_unknown")
        ledger = self.connection.execute(
            "SELECT running_actions FROM run_budget_ledger WHERE run_id = ?",
            (str(RUN_ID),),
        ).fetchone()
        self.assertEqual(int(ledger["running_actions"]), 0)

    def test_windows_job_assignment_failure_kills_worker_and_settles(self) -> None:
        self._seed()
        with patch(
            "nana_sidecar.storage.locked_unittest_executor.WindowsJob.assign",
            side_effect=RuntimeError("injected Job assignment failure"),
        ):
            result = self.service.execute(
                run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
            )
        self.assertEqual(result.result, "effect_unknown")
        self.assertEqual(self._receipt()["result"], "effect_unknown")
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT running_actions FROM run_budget_ledger WHERE run_id = ?",
                    (str(RUN_ID),),
                ).fetchone()["running_actions"]
            ),
            0,
        )

    def test_windows_job_resume_failure_kills_suspended_worker_and_settles(self) -> None:
        self._seed()

        class ResumeFailureJob:
            def resume(self, process) -> None:
                raise RuntimeError("injected Job resume failure")

            def terminate(self, process) -> bool:
                process.kill()
                process.wait(timeout=5)
                return True

            def close(self) -> None:
                return None

        with patch(
            "nana_sidecar.storage.locked_unittest_executor.WindowsJob.assign",
            return_value=ResumeFailureJob(),
        ):
            result = self.service.execute(
                run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
            )
        self.assertEqual(result.result, "effect_unknown")
        self.assertEqual(self._receipt()["result"], "effect_unknown")
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT running_actions FROM run_budget_ledger WHERE run_id = ?",
                    (str(RUN_ID),),
                ).fetchone()["running_actions"]
            ),
            0,
        )

    def test_observed_effect_escape_is_audited_as_violation(self) -> None:
        self._seed()

        def runner(*args, **kwargs):
            return LockedProcessResult(
                exit_code=0,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=1,
                actual_effects=EffectScope(network=("https://outside.invalid",)),
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
        )
        result = service.execute(
            run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
        )
        self.assertEqual(result.result, "effect_unknown")
        self.assertEqual(int(self._receipt()["effect_violation"]), 1)

    def test_running_cancel_produces_receipt_and_releases_reservation(self) -> None:
        self._seed()

        def runner(test_id, workspace_root, timeout_seconds, max_output_bytes, cancel):
            other = connect_database(self.path)
            try:
                outcome = RunSchedulerService(other, now=lambda: NOW_TEXT).cancel_run(
                    run_id=str(RUN_ID),
                    actor=self.actor,
                    reason="test running cancellation",
                )
                self.assertEqual(outcome.kind, "cancellation_requested")
            finally:
                other.close()
            self.assertTrue(cancel())
            return LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=1,
                cancelled=True,
                actual_effects=self.material["requested_effects"],
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
        )
        result = service.execute(
            run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
        )
        self.assertEqual(result.result, "effect_unknown")
        self.assertEqual(self._receipt()["result"], "effect_unknown")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM runs WHERE id = ?", (str(RUN_ID),)
            ).fetchone()["state"],
            "cancelled",
        )
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT running_actions FROM run_budget_ledger WHERE run_id = ?",
                    (str(RUN_ID),),
                ).fetchone()["running_actions"]
            ),
            0,
        )

    def test_orphaned_run_records_usage_and_releases_start_reservation(self) -> None:
        self._seed()

        def runner(*args, **kwargs):
            return LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=7,
                termination_failed=True,
                actual_effects=self.material["requested_effects"],
            )

        service = LockedUnittestExecutorService(
            self.connection,
            workspace_root=self.workspace_root,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
            run_unittest=runner,
        )
        result = service.execute(
            run_id=str(RUN_ID), action_id=str(ACTION_ID), actor=self.actor
        )
        self.assertEqual(result.result, "effect_unknown")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM runs WHERE id = ?", (str(RUN_ID),)
            ).fetchone()["state"],
            "orphaned",
        )
        ledger = self.connection.execute(
            """
            SELECT running_actions, usage_json
            FROM run_budget_ledger WHERE run_id = ?
            """,
            (str(RUN_ID),),
        ).fetchone()
        self.assertEqual(int(ledger["running_actions"]), 0)
        self.assertEqual(json.loads(str(ledger["usage_json"]))["wall_clock_ms"], 7)

    def test_worker_runtime_guards_block_real_forbidden_effects(self) -> None:
        for probe in (
            "network",
            "outside-read",
            "child-process",
            "write",
            "bytecode-disabled",
        ):
            with self.subTest(probe=probe):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "nana_sidecar.locked_unittest_worker",
                        "--probe",
                        probe,
                    ],
                    cwd=self.workspace_root,
                    env={},
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_combined_stdout_stderr_never_exceeds_shared_cap(self) -> None:
        class FakeJob:
            def resume(self, process):
                return None

            def close(self):
                return None

        class FakeProcess:
            def __init__(self, *args, **kwargs):
                self.stdout = io.BytesIO(b"x" * 256)
                self.stderr = io.BytesIO(b"y" * 256)
                self.returncode = None
                self.pid = 1

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

            def kill(self):
                self.returncode = -1

        with patch(
            "nana_sidecar.storage.locked_unittest_executor.subprocess.Popen",
            FakeProcess,
        ), patch(
            "nana_sidecar.storage.locked_unittest_executor.WindowsJob.assign",
            return_value=FakeJob(),
        ), patch(
            "nana_sidecar.storage.locked_unittest_executor._terminate_process_tree",
            return_value=True,
        ):
            result = __import__(
                "nana_sidecar.storage.locked_unittest_executor",
                fromlist=["default_locked_unittest_runner"],
            ).default_locked_unittest_runner(
                PYTHON_UNITTEST_LOCKED_TEST_IDS[0], self.workspace_root, 1, 100
            )
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout) + len(result.stderr), 100)

    def test_windows_worker_is_bound_before_suspended_process_resumes(self) -> None:
        calls: list[str] = []
        captured: dict[str, object] = {}

        class FakeProcess:
            def __init__(self, *args, **kwargs):
                captured["creationflags"] = kwargs["creationflags"]
                self.stdout = io.BytesIO(b"")
                self.stderr = io.BytesIO(b"")
                self.returncode = 0
                self.pid = 1

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.returncode = -1

        class FakeJob:
            def resume(self, process):
                calls.append("resume")

            def close(self):
                calls.append("close")

        def assign(process):
            calls.append("assign")
            return FakeJob()

        with patch(
            "nana_sidecar.storage.locked_unittest_executor.subprocess.Popen",
            FakeProcess,
        ), patch(
            "nana_sidecar.storage.locked_unittest_executor.WindowsJob.assign",
            side_effect=assign,
        ):
            result = __import__(
                "nana_sidecar.storage.locked_unittest_executor",
                fromlist=["default_locked_unittest_runner"],
            ).default_locked_unittest_runner(
                PYTHON_UNITTEST_LOCKED_TEST_IDS[0], self.workspace_root, 1, 100
            )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(calls, ["assign", "resume", "close"])
        self.assertTrue(int(captured["creationflags"]) & 0x00000004)

    def test_failed_windows_tree_kill_is_never_reported_as_verified(self) -> None:
        class FakeProcess:
            pid = 1

            def __init__(self):
                self.returncode = None
                self.killed = False

            def poll(self):
                return self.returncode

            def kill(self):
                self.killed = True
                self.returncode = -1

            def wait(self, timeout=None):
                return self.returncode

        process = FakeProcess()
        failed_taskkill = subprocess.CompletedProcess([], 1)
        with patch(
            "nana_sidecar.storage.locked_unittest_executor.os.name", "nt"
        ), patch(
            "nana_sidecar.storage.locked_unittest_executor.subprocess.run",
            return_value=failed_taskkill,
        ):
            terminated = __import__(
                "nana_sidecar.storage.locked_unittest_executor",
                fromlist=["_terminate_process_tree"],
            )._terminate_process_tree(process)
        self.assertFalse(terminated)
        self.assertTrue(process.killed)


if __name__ == "__main__":
    unittest.main()
