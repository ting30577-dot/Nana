"""D2-06 locked security corpus gate."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from nana_sidecar.contracts.authorization import (
    ActionHashMaterial,
    GrantMatchContext,
    approval_authorizes,
    canonical_json_hash,
    policy_grant_matches,
)
from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_CAPABILITY,
    PYTHON_UNITTEST_LOCKED_TEST_IDS,
    python_unittest_locked_registry_entry,
)
from nana_sidecar.contracts.capabilities import (
    CapabilityAuthorizationMode,
    CapabilityProviderMode,
    CapabilityRegistryEntry,
)
from nana_sidecar.contracts.common import (
    ActorKind,
    ActorRef,
    BudgetSnapshot,
    CapabilityRef,
    DataClass,
    EffectScope,
    RiskTier,
)
from nana_sidecar.contracts.domain import (
    Approval,
    ApprovalDecision,
    CapabilityConstraints,
    PolicyGrant,
    PolicyGrantState,
)
from nana_sidecar.contracts.locators import LineSpan, LocalFileCoordinates
from nana_sidecar.storage import (
    AdmissionStateError,
    LockedExecutorError,
    LockedProcessResult,
    LockedUnittestExecutorService,
)
from nana_sidecar.storage.artifacts import ArtifactIntegrityError, ArtifactStore
from nana_sidecar.storage.locked_unittest_executor import default_locked_unittest_runner
from nana_sidecar.storage.locked_unittest_executor import _run_locked_worker
from tests import test_d2_capability_admission as admission_fixtures
from tests import test_d2_locked_executor as executor_fixtures
from tests import test_d2_run_scheduler as scheduler_fixtures


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "fixtures" / "v0.3.0-dev" / "d2_security_corpus.json"
NOW_TEXT = "2026-08-01T00:00:00Z"
HASH = "sha256:" + "d" * 64
PROJECT_ID = UUID("60000000-0000-0000-0000-000000000001")


@dataclass(frozen=True, slots=True)
class CorpusOutcome:
    blocked: bool
    reason: str
    trace: dict[str, object]


def _budget(**changes: object) -> BudgetSnapshot:
    values: dict[str, object] = {
        "wall_clock_seconds": 60,
        "cpu_seconds": None,
        "memory_bytes": None,
        "gpu_seconds": None,
        "max_actions": 1,
        "max_concurrency": 1,
        "max_model_calls": 0,
        "max_model_tokens": 0,
        "max_cost_micros": 0,
        "max_retries": 0,
        "max_output_bytes": 4096,
        "max_artifact_bytes": 4096,
        "max_download_bytes": 0,
        "network_targets": (),
        "read_roots": ("project:source", "project:tests"),
        "write_roots": ("project:scratch",),
    }
    values.update(changes)
    return BudgetSnapshot(**values)


def _locked_material(**changes: object) -> ActionHashMaterial:
    args = changes.pop("args", {"test_id": PYTHON_UNITTEST_LOCKED_TEST_IDS[0]})
    values: dict[str, object] = {
        "capability": PYTHON_UNITTEST_LOCKED_CAPABILITY,
        "args": args,
        "args_hash": canonical_json_hash(args),
        "data_class": DataClass.PUBLIC,
        "provider": None,
        "requested_effects": EffectScope(
            reads=("project:source", "project:tests"),
            processes=("builtin:python.unittest.locked",),
        ),
        "network_methods": (),
        "budget": _budget(),
        "risk_tier": RiskTier.T2,
        "reversible": True,
    }
    values.update(changes)
    return ActionHashMaterial(**values)


def _grant(material: ActionHashMaterial, **constraint_changes: object) -> PolicyGrant:
    constraints_values: dict[str, object] = {
        "args_schema": python_unittest_locked_registry_entry().args_schema,
        "allowed_data_classes": (DataClass.PUBLIC,),
        "allowed_providers": (),
        "read_roots": ("project:source", "project:tests"),
        "write_roots": ("project:scratch",),
        "network_targets": (),
        "network_methods": (),
        "process_targets": ("builtin:python.unittest.locked",),
        "per_action_budget": material.budget,
        "cumulative_budget": material.budget,
        "max_concurrency": 1,
        "max_uses": 2,
        "valid_from": tests_now() - tests_delta(minutes=1),
        "expires_at": tests_now() + tests_delta(minutes=5),
    }
    constraints_values.update(constraint_changes)
    return PolicyGrant(
        id=uuid4(),
        project_id=PROJECT_ID,
        capability=material.capability,
        constraints=CapabilityConstraints(**constraints_values),
        state=PolicyGrantState.ACTIVE,
        uses=0,
        created_at=tests_now(),
    )


def tests_now():
    from datetime import datetime, timezone

    return datetime(2026, 8, 1, tzinfo=timezone.utc)


def tests_delta(**kwargs):
    from datetime import timedelta

    return timedelta(**kwargs)


def _context(material: ActionHashMaterial | None = None) -> GrantMatchContext:
    return GrantMatchContext(
        project_id=PROJECT_ID,
        projected_cumulative_budget=(material or _locked_material()).budget,
        current_concurrency=0,
    )


def _approval(action_id: UUID, material: ActionHashMaterial) -> Approval:
    return Approval(
        id=uuid4(),
        subject_type="action",
        subject_id=action_id,
        subject_hash=canonical_json_hash(material),
        capability=material.capability,
        parameter_summary={"test_id": "frozen"},
        requested_effects=material.requested_effects,
        data_class=material.data_class,
        provider=material.provider,
        budget=material.budget,
        risk_tier=material.risk_tier,
        reversible=material.reversible,
        allowed_uses=1,
        expires_at=tests_now() + tests_delta(minutes=5),
        decision=ApprovalDecision.APPROVED,
        decided_by=ActorRef(kind=ActorKind.USER, id="owner"),
        decided_at=tests_now(),
    )


def _auth_reason(material: ActionHashMaterial, registry_entry: CapabilityRegistryEntry) -> str:
    result = policy_grant_matches(
        _grant(material),
        material=material,
        registry_entry=registry_entry,
        context=_context(material),
        at=tests_now(),
    )
    return ",".join(result.reasons) if not result.matches else "AUTHORIZED"


def _blocked(case: dict[str, object], reason: str) -> CorpusOutcome:
    return CorpusOutcome(
        blocked=reason not in {"AUTHORIZED", "UNSAFE_PASS"},
        reason=reason,
        trace={
            "case_id": case["id"],
            "layer": case["layer"],
            "category": case["category"],
            "trace_ref": case["trace_ref"],
            "reason": reason,
        },
    )


class D2SecurityCorpusGateTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        self.evaluators: dict[str, Callable[[dict[str, object]], CorpusOutcome]] = {
            "admission_unregistered_capability": self._admission_unregistered_capability,
            "authorization_capability_digest_mismatch": self._authorization_capability_digest_mismatch,
            "authorization_args_schema_mismatch": self._authorization_args_schema_mismatch,
            "locator_parent_escape": self._locator_parent_escape,
            "artifact_final_symlink": self._artifact_final_symlink,
            "artifact_ancestor_junction": self._artifact_ancestor_junction,
            "authorization_shell_metacharacter_args": self._authorization_shell_metacharacter_args,
            "authorization_unauthorized_network": self._authorization_unauthorized_network,
            "authorization_provider_mismatch": self._authorization_provider_mismatch,
            "executor_timeout": self._executor_timeout,
            "executor_cancel_race": self._executor_cancel_race,
            "executor_oversized_output": self._executor_oversized_output,
            "scheduler_action_replay": self._scheduler_action_replay,
            "authorization_approval_expired": self._authorization_approval_expired,
            "authorization_approval_content_changed": self._authorization_approval_content_changed,
            "authorization_approval_replay": self._authorization_approval_replay,
            "authorization_never_grant_bypass": self._authorization_never_grant_bypass,
            "authorization_process_target_escape": self._authorization_process_target_escape,
            "executor_empty_environment": self._executor_empty_environment,
            "runtime_read_scope_guard": self._runtime_read_scope_guard,
            "runtime_write_scope_guard": self._runtime_write_scope_guard,
            "runtime_network_scope_guard": self._runtime_network_scope_guard,
            "runtime_process_scope_guard": self._runtime_process_scope_guard,
        }

    def test_corpus_metadata_and_category_coverage_are_frozen(self) -> None:
        self.assertEqual(self.corpus["schema_version"], 1)
        self.assertEqual(self.corpus["corpus_version"], "v0.3.0-dev-d2-06")
        self.assertEqual(
            self.corpus["seed"],
            "nana-d2-locked-security-corpus-2026-08-01",
        )
        cases = self.corpus["cases"]
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            set(self.corpus["required_categories"]),
            {case["category"] for case in cases},
        )
        self.assertEqual(
            {case["evaluator"] for case in cases},
            set(self.evaluators),
        )

    def test_every_security_counterexample_fails_closed_with_trace(self) -> None:
        unauthorized_high_risk_passes: list[str] = []
        traces: list[dict[str, object]] = []
        for case in self.corpus["cases"]:
            with self.subTest(case=case["id"]):
                outcome = self.evaluators[str(case["evaluator"])](case)
                traces.append(outcome.trace)
                self.assertTrue(outcome.blocked, outcome.trace)
                self.assertIn(str(case["expected_reason"]), outcome.reason)
                self.assertEqual(outcome.trace["case_id"], case["id"])
                self.assertEqual(outcome.trace["trace_ref"], case["trace_ref"])
                self.assertTrue(outcome.trace["reason"])
                if case["risk_class"] in {"T3", "T4", "T4-like"} and not outcome.blocked:
                    unauthorized_high_risk_passes.append(str(case["id"]))
        self.assertEqual(unauthorized_high_risk_passes, [])
        self.assertEqual(len(traces), len(self.corpus["cases"]))

    def _admission_unregistered_capability(self, case: dict[str, object]) -> CorpusOutcome:
        harness = admission_fixtures.D2CapabilityAdmissionTests(
            methodName="test_policy_grant_hit_authorizes_action_and_consumes_in_one_event"
        )
        harness.setUp()
        try:
            harness._seed_common()
            harness._insert_grant(harness._grant())
            with harness.connection:
                harness.connection.execute("DELETE FROM capability_registry_entries")
            try:
                harness.service.authorize_with_policy_grant(
                    action_id=str(admission_fixtures.ACTION_ID),
                    grant_id=str(admission_fixtures.GRANT_ID),
                    material=harness.material,
                    context=harness._context(),
                    actor=harness.actor,
                )
            except AdmissionStateError as exc:
                return _blocked(case, exc.code)
            return _blocked(case, "UNSAFE_PASS")
        finally:
            harness.tearDown()

    def _authorization_capability_digest_mismatch(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(
            capability=CapabilityRef(
                id=PYTHON_UNITTEST_LOCKED_CAPABILITY.id,
                version=PYTHON_UNITTEST_LOCKED_CAPABILITY.version,
                digest="sha256:" + "e" * 64,
            )
        )
        return _blocked(case, _auth_reason(material, python_unittest_locked_registry_entry()))

    def _authorization_args_schema_mismatch(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(args={"test_id": "tests.not_allowed.Case.test"})
        return _blocked(case, _auth_reason(material, python_unittest_locked_registry_entry()))

    def _locator_parent_escape(self, case: dict[str, object]) -> CorpusOutcome:
        try:
            LocalFileCoordinates(
                artifact_hash=HASH,
                logical_path="../secret.txt",
                line_span=LineSpan(start_line=1, end_line=1),
            )
        except ValidationError as exc:
            return _blocked(case, str(exc))
        return _blocked(case, "UNSAFE_PASS")

    def _artifact_final_symlink(self, case: dict[str, object]) -> CorpusOutcome:
        with tempfile.TemporaryDirectory() as raw:
            store = ArtifactStore(Path(raw) / "workspace")
            staged = store.stage_bytes(b"do not follow links", "text/plain")
            final_path = store.blob_path(staged.blob_hash)
            final_path.parent.mkdir(parents=True)
            final_path.write_bytes(b"do not follow links")
            with patch.object(Path, "is_symlink", return_value=True):
                try:
                    store.promote(staged)
                except ArtifactIntegrityError as exc:
                    return _blocked(case, str(exc))
        return _blocked(case, "UNSAFE_PASS")

    def _artifact_ancestor_junction(self, case: dict[str, object]) -> CorpusOutcome:
        with tempfile.TemporaryDirectory() as raw:
            store = ArtifactStore(Path(raw) / "workspace")
            store.artifacts_root.mkdir(parents=True)
            real_isjunction = getattr(os.path, "isjunction", lambda path: False)

            def injected_isjunction(path: object) -> bool:
                return Path(path) == store.artifacts_root or real_isjunction(path)

            with patch.object(
                os.path,
                "isjunction",
                side_effect=injected_isjunction,
                create=True,
            ):
                try:
                    store.stage_bytes(b"must stay in Workspace", "text/plain")
                except ArtifactIntegrityError as exc:
                    return _blocked(case, str(exc))
        return _blocked(case, "UNSAFE_PASS")

    def _authorization_shell_metacharacter_args(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(args={"test_id": "tests.safe.Case.test; whoami"})
        return _blocked(case, _auth_reason(material, python_unittest_locked_registry_entry()))

    def _authorization_unauthorized_network(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(
            requested_effects=EffectScope(
                reads=("project:source", "project:tests"),
                writes=("project:scratch",),
                network=("https://example.test",),
                processes=("builtin:python.unittest.locked",),
            ),
            network_methods=("GET",),
        )
        return _blocked(case, _auth_reason(material, python_unittest_locked_registry_entry()))

    def _authorization_provider_mismatch(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(provider="local-model")
        return _blocked(case, _auth_reason(material, python_unittest_locked_registry_entry()))

    def _executor_timeout(self, case: dict[str, object]) -> CorpusOutcome:
        result = _run_locked_worker(
            ["--probe", "sleep"],
            ROOT,
            0.01,
            4096,
        )
        return _blocked(case, "timed_out" if result.timed_out else "UNSAFE_PASS")

    def _executor_cancel_race(self, case: dict[str, object]) -> CorpusOutcome:
        result = _run_locked_worker(
            ["--probe", "sleep"],
            ROOT,
            10,
            4096,
            lambda: True,
        )
        return _blocked(case, "cancelled" if result.cancelled else "UNSAFE_PASS")

    def _executor_oversized_output(self, case: dict[str, object]) -> CorpusOutcome:
        result = _run_locked_worker(
            ["--probe", "output"],
            ROOT,
            10,
            1024,
        )
        blocked = result.output_truncated and len(result.stdout) + len(result.stderr) <= 1024
        return _blocked(case, "output_truncated" if blocked else "UNSAFE_PASS")

    def _runtime_probe(
        self,
        case: dict[str, object],
        probe: str,
    ) -> CorpusOutcome:
        result = _run_locked_worker(["--probe", probe], ROOT, 5, 4096)
        reason = f"runtime_guard:{probe}" if result.exit_code == 0 else "UNSAFE_PASS"
        return _blocked(case, reason)

    def _runtime_read_scope_guard(self, case: dict[str, object]) -> CorpusOutcome:
        return self._runtime_probe(case, "outside-read")

    def _runtime_write_scope_guard(self, case: dict[str, object]) -> CorpusOutcome:
        return self._runtime_probe(case, "write")

    def _runtime_network_scope_guard(self, case: dict[str, object]) -> CorpusOutcome:
        return self._runtime_probe(case, "network")

    def _runtime_process_scope_guard(self, case: dict[str, object]) -> CorpusOutcome:
        return self._runtime_probe(case, "child-process")

    def _scheduler_action_replay(self, case: dict[str, object]) -> CorpusOutcome:
        harness = scheduler_fixtures.D2RunSchedulerTests(
            methodName="test_claim_authorized_action_once_and_records_started_event"
        )
        harness.setUp()
        try:
            harness._seed()
            harness.service.claim_action(
                run_id="run-1",
                action_id="action-1",
                actor=harness.actor,
            )
            try:
                harness.service.claim_action(
                    run_id="run-1",
                    action_id="action-1",
                    actor=harness.actor,
                )
            except Exception as exc:
                return _blocked(case, getattr(exc, "code", str(exc)))
            return _blocked(case, "UNSAFE_PASS")
        finally:
            harness.tearDown()

    def _authorization_approval_expired(self, case: dict[str, object]) -> CorpusOutcome:
        action_id = uuid4()
        material = _locked_material()
        approval = _approval(action_id, material)
        result = approval_authorizes(
            approval,
            action_id=action_id,
            material=material,
            registry_entry=python_unittest_locked_registry_entry().model_copy(
                update={
                    "authorization_mode": CapabilityAuthorizationMode.ONE_TIME_APPROVAL,
                    "grantable": False,
                }
            ),
            at=approval.expires_at,
            prior_uses=0,
        )
        return _blocked(case, ",".join(result.reasons) if not result.matches else "AUTHORIZED")

    def _authorization_approval_content_changed(self, case: dict[str, object]) -> CorpusOutcome:
        action_id = uuid4()
        material = _locked_material()
        approval = _approval(action_id, material)
        changed = _locked_material(args={"test_id": "tests.changed.Case.test"})
        result = approval_authorizes(
            approval,
            action_id=action_id,
            material=changed,
            registry_entry=python_unittest_locked_registry_entry().model_copy(
                update={
                    "authorization_mode": CapabilityAuthorizationMode.ONE_TIME_APPROVAL,
                    "grantable": False,
                }
            ),
            at=tests_now(),
            prior_uses=0,
        )
        return _blocked(case, ",".join(result.reasons) if not result.matches else "AUTHORIZED")

    def _authorization_approval_replay(self, case: dict[str, object]) -> CorpusOutcome:
        action_id = uuid4()
        material = _locked_material()
        approval = _approval(action_id, material)
        result = approval_authorizes(
            approval,
            action_id=action_id,
            material=material,
            registry_entry=python_unittest_locked_registry_entry().model_copy(
                update={
                    "authorization_mode": CapabilityAuthorizationMode.ONE_TIME_APPROVAL,
                    "grantable": False,
                }
            ),
            at=tests_now(),
            prior_uses=1,
        )
        return _blocked(case, ",".join(result.reasons) if not result.matches else "AUTHORIZED")

    def _authorization_never_grant_bypass(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(
            capability=CapabilityRef(id="export.publish", version="1", digest=HASH),
            risk_tier=RiskTier.T4,
            reversible=False,
        )
        registry_entry = CapabilityRegistryEntry(
            capability=material.capability,
            args_schema=python_unittest_locked_registry_entry().args_schema,
            risk_tier=RiskTier.T4,
            reversible=False,
            authorization_mode=CapabilityAuthorizationMode.ONE_TIME_APPROVAL,
            grantable=False,
            provider_mode=CapabilityProviderMode.FORBIDDEN,
            allowed_providers=(),
            read_roots=material.requested_effects.reads,
            write_roots=material.requested_effects.writes,
            network_targets=material.requested_effects.network,
            network_methods=material.network_methods,
            process_targets=material.requested_effects.processes,
            timeout_seconds=60,
        )
        return _blocked(case, _auth_reason(material, registry_entry))

    def _authorization_process_target_escape(self, case: dict[str, object]) -> CorpusOutcome:
        material = _locked_material(
            requested_effects=EffectScope(
                reads=("project:source", "project:tests"),
                writes=("project:scratch",),
                processes=("builtin:powershell",),
            )
        )
        return _blocked(case, _auth_reason(material, python_unittest_locked_registry_entry()))

    def _executor_empty_environment(self, case: dict[str, object]) -> CorpusOutcome:
        captured: dict[str, object] = {}

        class FakeJob:
            def resume(self, process) -> None:
                return None

            def close(self) -> None:
                return None

        class FakeProcess:
            def __init__(self, *args, **kwargs) -> None:
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.stdout = io.BytesIO(b"")
                self.stderr = io.BytesIO(b"")
                self.returncode = 0
                self.pid = 1

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return 0

            def terminate(self) -> None:
                self.returncode = -1

            def kill(self) -> None:
                self.returncode = -1

        with patch(
            "nana_sidecar.storage.locked_unittest_executor.subprocess.Popen",
            FakeProcess,
        ), patch(
            "nana_sidecar.storage.locked_unittest_executor.WindowsJob.assign",
            return_value=FakeJob(),
        ):
            result = default_locked_unittest_runner(
                PYTHON_UNITTEST_LOCKED_TEST_IDS[0],
                ROOT,
                1,
                1024,
            )
        kwargs = captured.get("kwargs")
        if (
            result.exit_code == 0
            and isinstance(kwargs, dict)
            and kwargs.get("env") == {}
            and kwargs.get("shell") is False
        ):
            return _blocked(case, "env_empty")
        return _blocked(case, "UNSAFE_PASS")


if __name__ == "__main__":
    unittest.main()
