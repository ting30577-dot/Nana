"""D2-04 locked local executor for ``python.unittest.locked``.

This executor is intentionally narrow: it can run only the frozen unittest IDs
declared by the built-in Capability registry.  It is not a general sandbox and
does not execute arbitrary user-provided code.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_CAPABILITY,
    PYTHON_UNITTEST_LOCKED_TEST_IDS,
)
from nana_sidecar.contracts.authorization import ActionHashMaterial, compute_action_hash
from nana_sidecar.contracts.capabilities import CapabilityRegistryEntry
from nana_sidecar.contracts.common import (
    ActorRef,
    EffectScope,
    ResourceUsage,
    effect_scope_is_subset,
)
from nana_sidecar.contracts.domain import AuthorizationSource
from nana_sidecar.storage.budget_accounting import (
    BudgetAccountingError,
    BudgetAccountingService,
)
from nana_sidecar.storage.run_scheduler import RunSchedulerService, SchedulerStateError
from nana_sidecar.storage.windows_job import WINDOWS_CREATE_SUSPENDED, WindowsJob


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class LockedExecutorError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class LockedProcessResult:
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    wall_clock_ms: int
    timed_out: bool = False
    output_truncated: bool = False
    cancelled: bool = False
    termination_failed: bool = False
    runner_error: bool = False
    pre_spawn_cancelled: bool = False
    actual_effects: EffectScope | None = None


@dataclass(frozen=True, slots=True)
class LockedExecutorResult:
    action_id: str
    receipt_id: str
    result: str
    event_ids: tuple[int, ...]


ArgsArtifactLoader = Callable[[sqlite3.Row], bytes]
LockedUnittestRunner = Callable[
    [str, Path, float, int, Callable[[], bool]],
    LockedProcessResult,
]
BeforeProcessStart = Callable[[], None]


class LockedUnittestExecutorService:
    """Claim and execute a single locked unittest Action."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_root: str | Path,
        now: Callable[[], str],
        load_args_artifact: ArgsArtifactLoader,
        run_unittest: LockedUnittestRunner | None = None,
        before_process_start: BeforeProcessStart | None = None,
    ) -> None:
        self.connection = connection
        self.workspace_root = Path(workspace_root).resolve(strict=False)
        self._now = now
        self._load_args_artifact = load_args_artifact
        self._run_unittest = run_unittest or default_locked_unittest_runner
        self._before_process_start = before_process_start

    def execute(
        self,
        *,
        run_id: str,
        action_id: str,
        actor: ActorRef,
    ) -> LockedExecutorResult:
        preflight = self._preflight_authorized_action(run_id, action_id)
        scheduler = RunSchedulerService(self.connection, now=self._now)
        try:
            started = scheduler.claim_action(
                run_id=run_id,
                action_id=action_id,
                actor=actor,
            )
        except SchedulerStateError as exc:
            raise LockedExecutorError(exc.code, str(exc)) from exc

        self._require_still_running(action_id)
        if self._before_process_start is not None:
            self._before_process_start()
        self._require_still_running(action_id)
        started_at = time.monotonic()
        try:
            process = self._run_unittest(
                preflight["test_id"],
                self.workspace_root,
                preflight["timeout_seconds"],
                preflight["max_output_bytes"],
                lambda: self._run_is_cancel_requested(run_id, action_id),
            )
        except Exception:
            process = LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=int((time.monotonic() - started_at) * 1000),
                runner_error=True,
                actual_effects=EffectScope(),
            )
        return self._record_completion(
            action_id=action_id,
            run_id=run_id,
            actor=actor,
            started_event_ids=started.event_ids,
            preflight=preflight,
            process=process,
        )

    def _preflight_authorized_action(
        self,
        run_id: str,
        action_id: str,
        *,
        allow_running: bool = False,
    ) -> dict[str, object]:
        row = self.connection.execute(
            """
            SELECT
                actions.id,
                actions.run_id,
                actions.capability_id,
                actions.capability_version,
                actions.executable_digest,
                actions.args_artifact_id,
                actions.args_hash,
                actions.action_hash,
                actions.risk_tier,
                actions.requested_effects_json,
                actions.authorization_ref,
                actions.state,
                runs.snapshot_json,
                action_authorizations.action_hash AS authorized_action_hash,
                action_authorizations.material_json,
                action_authorizations.registry_contract_digest,
                action_authorizations.authorization_source,
                action_authorizations.authorization_ref AS durable_authorization_ref
            FROM actions
            JOIN runs ON runs.id = actions.run_id
            LEFT JOIN action_authorizations
              ON action_authorizations.action_id = actions.id
            WHERE actions.id = ?
            """,
            (action_id,),
        ).fetchone()
        if row is None:
            raise LockedExecutorError("E_ACTION_NOT_FOUND", "Action does not exist")
        if str(row["run_id"]) != run_id:
            raise LockedExecutorError(
                "E_ACTION_RUN_MISMATCH",
                "Action does not belong to Run",
            )
        allowed_states = {"authorized", "running"} if allow_running else {"authorized"}
        if str(row["state"]) not in allowed_states:
            raise LockedExecutorError(
                "E_ACTION_NOT_AUTHORIZED",
                "Locked executor can only run authorized Actions",
            )
        if (
            str(row["capability_id"]) != PYTHON_UNITTEST_LOCKED_CAPABILITY.id
            or str(row["capability_version"])
            != PYTHON_UNITTEST_LOCKED_CAPABILITY.version
            or str(row["executable_digest"])
            != PYTHON_UNITTEST_LOCKED_CAPABILITY.digest
        ):
            raise LockedExecutorError(
                "E_LOCKED_CAPABILITY_MISMATCH",
                "Action is not python.unittest.locked with the frozen digest",
            )

        registry_entry = self._require_registry_entry()
        if row["material_json"] is None:
            raise LockedExecutorError(
                "E_ACTION_AUTHORIZATION_MISSING",
                "Action has no durable authorization material",
            )
        try:
            material = ActionHashMaterial.model_validate_json(str(row["material_json"]))
        except ValueError as exc:
            raise LockedExecutorError(
                "E_ACTION_AUTHORIZATION_INVALID",
                "Durable authorization material is invalid",
            ) from exc
        args = self._load_canonical_args(
            str(row["args_artifact_id"]),
            max_size=material.budget.max_artifact_bytes,
        )
        if args.get("test_id") not in PYTHON_UNITTEST_LOCKED_TEST_IDS:
            raise LockedExecutorError(
                "E_LOCKED_TEST_ID",
                "test_id is not in the frozen unittest allowlist",
            )
        requested_effects = EffectScope.model_validate_json(
            str(row["requested_effects_json"])
        )
        expected_effects = EffectScope(
            reads=registry_entry.read_roots,
            processes=registry_entry.process_targets,
        )
        if requested_effects != expected_effects:
            raise LockedExecutorError(
                "E_LOCKED_EFFECT_SCOPE",
                "Action effects do not match locked unittest execution ceiling",
            )
        if material.args != args or material.args_hash != str(row["args_hash"]):
            raise LockedExecutorError(
                "E_ACTION_AUTHORIZATION_MISMATCH",
                "Authorized args do not match the Action args artifact",
            )
        if material.requested_effects != requested_effects:
            raise LockedExecutorError(
                "E_ACTION_AUTHORIZATION_MISMATCH",
                "Authorized effects do not match persisted Action effects",
            )
        computed_action_hash = compute_action_hash(material)
        if (
            computed_action_hash != str(row["action_hash"])
            or computed_action_hash != str(row["authorized_action_hash"])
            or str(row["registry_contract_digest"]) != registry_entry.contract_digest
            or str(row["durable_authorization_ref"]) != str(row["authorization_ref"])
        ):
            raise LockedExecutorError(
                "E_ACTION_AUTHORIZATION_MISMATCH",
                "Durable authorization binding does not match the Action",
            )
        expected_source = (
            "policy_grant"
            if str(row["authorization_ref"]).startswith("policy_grant:")
            else "approval"
            if str(row["authorization_ref"]).startswith("approval:")
            else None
        )
        if expected_source != str(row["authorization_source"]):
            raise LockedExecutorError(
                "E_ACTION_AUTHORIZATION_MISMATCH",
                "Authorization source and reference disagree",
            )
        if str(row["args_hash"]) != _canonical_json_hash(args):
            raise LockedExecutorError(
                "E_ARGS_HASH_MISMATCH",
                "Action args_hash does not match args artifact JSON",
            )
        if not str(row["authorization_ref"]).strip():
            raise LockedExecutorError(
                "E_AUTHORIZATION_REF_REQUIRED",
                "Authorized Action must retain authorization_ref",
            )
        try:
            run_budget = json.loads(str(row["snapshot_json"]))["budget"]
            run_wall_clock_seconds = int(run_budget["wall_clock_seconds"])
            run_max_output_bytes = int(run_budget["max_output_bytes"])
            run_max_artifact_bytes = int(run_budget["max_artifact_bytes"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LockedExecutorError(
                "E_RUN_BUDGET_INVALID",
                "Run snapshot does not contain an executable budget",
            ) from exc
        timeout_seconds = min(
            int(registry_entry.timeout_seconds or material.budget.wall_clock_seconds),
            material.budget.wall_clock_seconds,
            run_wall_clock_seconds,
        )
        max_output_bytes = min(
            material.budget.max_output_bytes,
            run_max_output_bytes,
        )
        max_artifact_bytes = min(
            material.budget.max_artifact_bytes,
            run_max_artifact_bytes,
        )
        return {
            "action_hash": str(row["action_hash"]),
            "args_hash": str(row["args_hash"]),
            "capability_digest": str(row["executable_digest"]),
            "authorization_ref": str(row["authorization_ref"]),
            "authorized_effects": requested_effects,
            "test_id": str(args["test_id"]),
            "timeout_seconds": timeout_seconds,
            "max_output_bytes": max_output_bytes,
            "max_artifact_bytes": max_artifact_bytes,
        }

    def _require_registry_entry(self) -> CapabilityRegistryEntry:
        row = self.connection.execute(
            """
            SELECT executable_digest, entry_json, contract_digest
            FROM capability_registry_entries
            WHERE capability_id = ?
              AND capability_version = ?
              AND executable_digest = ?
            """,
            (
                PYTHON_UNITTEST_LOCKED_CAPABILITY.id,
                PYTHON_UNITTEST_LOCKED_CAPABILITY.version,
                PYTHON_UNITTEST_LOCKED_CAPABILITY.digest,
            ),
        ).fetchone()
        if row is None:
            raise LockedExecutorError(
                "E_LOCKED_CAPABILITY_UNREGISTERED",
                "python.unittest.locked is not registered",
            )
        entry = CapabilityRegistryEntry.model_validate_json(str(row["entry_json"]))
        if (
            entry.capability != PYTHON_UNITTEST_LOCKED_CAPABILITY
            or str(row["executable_digest"]) != entry.capability.digest
            or str(row["contract_digest"]) != entry.contract_digest
        ):
            raise LockedExecutorError(
                "E_LOCKED_REGISTRY_MISMATCH",
                "python.unittest.locked registry row is inconsistent",
            )
        return entry

    def _load_canonical_args(
        self,
        artifact_id: str,
        *,
        max_size: int,
    ) -> dict[str, object]:
        artifact = self.connection.execute(
            """
            SELECT id, media_type, blob_hash, size, state
            FROM artifacts
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if artifact is None:
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_NOT_FOUND",
                "Args Artifact does not exist",
            )
        if str(artifact["state"]) != "available":
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_UNAVAILABLE",
                "Args Artifact is not available",
            )
        if str(artifact["media_type"]) != "application/json":
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_MEDIA_TYPE",
                "Args Artifact must be application/json",
            )
        raw = self._load_args_artifact(artifact)
        if len(raw) != int(artifact["size"]):
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_SIZE",
                "Args Artifact bytes do not match its persisted size",
            )
        if len(raw) > max_size:
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_BUDGET",
                "Args Artifact exceeds the authorized artifact budget",
            )
        if f"sha256:{hashlib.sha256(raw).hexdigest()}" != str(artifact["blob_hash"]):
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_HASH",
                "Args Artifact bytes do not match persisted blob hash",
            )
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_JSON",
                "Args Artifact is not valid JSON",
            ) from exc
        if not isinstance(value, dict):
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_JSON",
                "Args Artifact must be a JSON object",
            )
        return value

    def _require_still_running(self, action_id: str) -> None:
        state = self.connection.execute(
            "SELECT state FROM actions WHERE id = ?",
            (action_id,),
        ).fetchone()
        if state is None or str(state["state"]) != "running":
            raise LockedExecutorError(
                "E_ACTION_CANCEL_RACE",
                "Action was cancelled before process start",
            )

    def _run_is_cancel_requested(self, run_id: str, action_id: str) -> bool:
        row = self.connection.execute(
            """
            SELECT runs.state AS run_state, runs.result_json, actions.state AS action_state
            FROM runs
            JOIN actions ON actions.run_id = runs.id
            WHERE runs.id = ? AND actions.id = ?
            """,
            (run_id, action_id),
        ).fetchone()
        if row is None or str(row["action_state"]) != "running":
            return True
        if str(row["run_state"]) != "paused":
            return False
        try:
            result = json.loads(str(row["result_json"] or "{}"))
        except json.JSONDecodeError:
            return True
        return result.get("reason") == "cancel_requested"

    def _record_completion(
        self,
        *,
        action_id: str,
        run_id: str,
        actor: ActorRef,
        started_event_ids: tuple[int, ...],
        preflight: dict[str, object],
        process: LockedProcessResult,
        after_artifact_ids: tuple[str, ...] = (),
        after_artifact_relation_ids: tuple[str, ...] = (),
        settle_terminal_run: bool = False,
        causation_id: str | None = None,
        publish_output_artifacts: Callable[[], tuple[int, ...]] | None = None,
    ) -> LockedExecutorResult:
        authorized_effects = preflight["authorized_effects"]
        if not isinstance(authorized_effects, EffectScope):
            raise TypeError("authorized_effects must be EffectScope")
        actual_effects = process.actual_effects or EffectScope()
        effect_violation = not effect_scope_is_subset(actual_effects, authorized_effects)
        if process.pre_spawn_cancelled:
            action_state = "cancelled"
            receipt_result = "cancelled"
            event_type = "action.cancelled"
            reason = "cancelled_before_process_start"
        elif effect_violation:
            action_state = "effect_unknown"
            receipt_result = "effect_unknown"
            event_type = "action.effect_unknown"
            reason = "effect_scope_violation"
        elif process.termination_failed:
            action_state = "effect_unknown"
            receipt_result = "effect_unknown"
            event_type = "action.effect_unknown"
            reason = "process_tree_termination_failed"
        elif process.runner_error:
            action_state = "effect_unknown"
            receipt_result = "effect_unknown"
            event_type = "action.effect_unknown"
            reason = "runner_error"
        elif process.cancelled:
            action_state = "effect_unknown"
            receipt_result = "effect_unknown"
            event_type = "action.effect_unknown"
            reason = "cancelled_after_process_start"
        elif process.output_truncated:
            action_state = "effect_unknown"
            receipt_result = "effect_unknown"
            event_type = "action.effect_unknown"
            reason = "output_cap_exceeded"
        elif process.timed_out:
            action_state = "timed_out"
            receipt_result = "timed_out"
            event_type = "action.completed"
            reason = "timeout"
        elif process.exit_code == 0:
            action_state = "succeeded"
            receipt_result = "succeeded"
            event_type = "action.completed"
            reason = "exit_zero"
        else:
            action_state = "failed"
            receipt_result = "failed"
            event_type = "action.completed"
            reason = "exit_nonzero"

        receipt_id = str(uuid4())
        occurred_at = self._now()
        resource_usage = ResourceUsage(
            wall_clock_ms=process.wall_clock_ms,
            output_bytes=len(process.stdout) + len(process.stderr),
        )
        with self._transaction():
            artifact_publish_event_ids = (
                publish_output_artifacts()
                if publish_output_artifacts is not None
                else ()
            )
            self._require_output_artifacts(
                run_id,
                after_artifact_ids,
                max_artifact_bytes=int(preflight.get("max_artifact_bytes", 0)),
            )
            artifact_event_ids = self._attach_output_artifacts(
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                artifact_ids=after_artifact_ids,
                relation_ids=after_artifact_relation_ids,
                occurred_at=occurred_at,
                causation_id=causation_id,
            )
            updated = self.connection.execute(
                """
                UPDATE actions
                SET state = ?, finished_at = ?
                WHERE id = ? AND state = 'running'
                """,
                (action_state, occurred_at, action_id),
            )
            if updated.rowcount != 1:
                raise LockedExecutorError(
                    "E_ACTION_COMPLETE_RACE",
                    "Action changed before locked executor completion",
                )
            receipt_source, approved_by, approved_at = self._authorization_provenance(
                str(preflight["authorization_ref"])
            )
            self.connection.execute(
                """
                INSERT INTO action_receipts (
                    id, action_id, action_hash, authorization_source,
                    authorization_ref, approved_by_json, approved_at,
                    actual_effects_json, result, exit_code,
                    before_artifact_ids_json, after_artifact_ids_json,
                    resource_usage_json, created_at, authorized_effects_json,
                    effect_violation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    action_id,
                    str(preflight["action_hash"]),
                    receipt_source.value,
                    str(preflight["authorization_ref"]),
                    None if approved_by is None else _json(approved_by),
                    approved_at,
                    _json(actual_effects.model_dump(mode="json")),
                    receipt_result,
                    process.exit_code,
                    _json(list(after_artifact_ids)),
                    _json(resource_usage.model_dump(mode="json")),
                    occurred_at,
                    _json(authorized_effects.model_dump(mode="json")),
                    1 if effect_violation else 0,
                ),
            )
            try:
                budget_result = BudgetAccountingService(
                    self.connection,
                    now=self._now,
                ).record_action_usage(
                    run_id=run_id,
                    action_id=action_id,
                    usage=resource_usage,
                    actor=actor,
                )
            except BudgetAccountingError as exc:
                raise LockedExecutorError(exc.code, str(exc)) from exc
            event_id = self._append_event(
                aggregate_type="action",
                aggregate_id=action_id,
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                event_type=event_type,
                payload={
                    "action_id": action_id,
                    "state": action_state,
                    "result": receipt_result,
                    "receipt_id": receipt_id,
                    "reason": reason,
                    "exit_code": process.exit_code,
                    "stdout_bytes": len(process.stdout),
                    "stderr_bytes": len(process.stderr),
                    "billing_basis": self._billing_basis(
                        process=process,
                        receipt_result=receipt_result,
                    ),
                },
                occurred_at=occurred_at,
                causation_id=causation_id,
            )
            gate_event_ids = self._append_gate_audit_events(
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                preflight=preflight,
                process=process,
                effect_decision=receipt_result,
                occurred_at=occurred_at,
                causation_id=causation_id,
            ) if causation_id is not None else ()
            run_event_id = (
                self._settle_terminal_run_after_process(
                    run_id=run_id,
                    action_id=action_id,
                    actor=actor,
                    process=process,
                    receipt_result=receipt_result,
                    occurred_at=occurred_at,
                    causation_id=causation_id,
                )
                if settle_terminal_run
                else self._settle_run_after_process(
                    run_id=run_id,
                    action_id=action_id,
                    actor=actor,
                    process=process,
                    occurred_at=occurred_at,
                    causation_id=causation_id,
                )
            )
            terminal_event_ids = (event_id,) if run_event_id is None else (event_id, run_event_id)
        return LockedExecutorResult(
            action_id=action_id,
            receipt_id=receipt_id,
            result=receipt_result,
            event_ids=(
                started_event_ids
                + artifact_publish_event_ids
                + artifact_event_ids
                + budget_result.event_ids
                + gate_event_ids
                + terminal_event_ids
            ),
        )

    def _require_output_artifacts(
        self,
        run_id: str,
        artifact_ids: tuple[str, ...],
        *,
        max_artifact_bytes: int,
    ) -> None:
        if len(artifact_ids) != len(set(artifact_ids)):
            raise LockedExecutorError(
                "E_RESULT_ARTIFACT_DUPLICATE",
                "Receipt output Artifacts must be unique",
            )
        total = 0
        for artifact_id in artifact_ids:
            row = self.connection.execute(
                "SELECT state, producer_run_id, size FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            if (
                row is None
                or str(row["state"]) != "available"
                or row["producer_run_id"] not in (None, run_id)
            ):
                raise LockedExecutorError(
                    "E_RESULT_ARTIFACT_UNAVAILABLE",
                    "Receipt output Artifact is unavailable or has the wrong producer",
                )
            total += int(row["size"])
        if total > max_artifact_bytes:
            raise LockedExecutorError(
                "E_RESULT_ARTIFACT_BUDGET",
                "Receipt output Artifacts exceed the authorized budget",
            )

    def _attach_output_artifacts(
        self,
        *,
        run_id: str,
        action_id: str,
        actor: ActorRef,
        artifact_ids: tuple[str, ...],
        relation_ids: tuple[str, ...],
        occurred_at: str,
        causation_id: str | None,
    ) -> tuple[int, ...]:
        if len(artifact_ids) != len(relation_ids):
            raise LockedExecutorError(
                "E_RESULT_RELATION_COUNT",
                "Every Receipt output Artifact requires one provenance Relation",
            )
        event_ids: list[int] = []
        for artifact_id, relation_id in zip(artifact_ids, relation_ids, strict=True):
            attached = self.connection.execute(
                "UPDATE artifacts SET producer_run_id = ? "
                "WHERE id = ? AND producer_run_id IS NULL",
                (run_id, artifact_id),
            )
            if attached.rowcount != 1:
                producer = self.connection.execute(
                    "SELECT producer_run_id FROM artifacts WHERE id = ?",
                    (artifact_id,),
                ).fetchone()
                if producer is None or str(producer["producer_run_id"]) != run_id:
                    raise LockedExecutorError(
                        "E_RESULT_ARTIFACT_PRODUCER",
                        "Receipt output Artifact has a conflicting producer",
                    )
            existing = self.connection.execute(
                "SELECT type, source_type, source_id, target_type, target_id, "
                "producer_run_id, status FROM relations WHERE id = ?",
                (relation_id,),
            ).fetchone()
            expected = (
                "run_produces_artifact",
                "run",
                run_id,
                "artifact",
                artifact_id,
                run_id,
                "active",
            )
            if existing is not None:
                if tuple(existing) != expected:
                    raise LockedExecutorError(
                        "E_RESULT_RELATION_MISMATCH",
                        "Locked result provenance Relation changed",
                    )
                continue
            self.connection.execute(
                "INSERT INTO relations(id, type, source_type, source_id, target_type, "
                "target_id, producer_run_id, created_by_json, status) "
                "VALUES (?, 'run_produces_artifact', 'run', ?, 'artifact', ?, ?, ?, 'active')",
                (
                    relation_id,
                    run_id,
                    artifact_id,
                    run_id,
                    _json(actor.model_dump(mode="json")),
                ),
            )
            event_ids.append(self._append_event(
                aggregate_type="relation",
                aggregate_id=relation_id,
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                event_type="relation.created",
                payload={
                    "relation_id": relation_id,
                    "relation_type": "run_produces_artifact",
                    "source_id": run_id,
                    "target_id": artifact_id,
                    "status": "active",
                },
                occurred_at=occurred_at,
                causation_id=causation_id,
            ))
        return tuple(event_ids)

    @staticmethod
    def _billing_basis(
        *,
        process: LockedProcessResult,
        receipt_result: str,
    ) -> str:
        if process.pre_spawn_cancelled:
            return "not_charged_pre_spawn"
        if receipt_result in {"effect_unknown", "timed_out"}:
            return "conservative_uncertain_effect"
        return "measured_observed_effect"

    def _append_gate_audit_events(
        self,
        *,
        run_id: str,
        action_id: str,
        actor: ActorRef,
        preflight: dict[str, object],
        process: LockedProcessResult,
        effect_decision: str,
        occurred_at: str,
        causation_id: str,
    ) -> tuple[int, ...]:
        """Persist the accepted D3-06 Gate-A..H decision record atomically."""

        common = {
            "action_id": action_id,
            "phase": "gate_decision",
            "fixture_digest": str(preflight["args_hash"]),
            "capability_digest": str(preflight["capability_digest"]),
            "effect_decision": effect_decision,
            "billing_basis": self._billing_basis(
                process=process,
                receipt_result=effect_decision,
            ),
        }
        gate_sources = {
            "Gate-A": "verified_args_artifact_and_authorization_material",
            "Gate-B": "locked_executor_contract",
            "Gate-C": "durable_action_lifecycle",
            "Gate-D": "d2_budget_reservation_and_settlement",
            "Gate-E": "terminal_receipt_artifact_visibility_transaction",
            "Gate-F": "owner_lane_worker_bridge",
            "Gate-H": "append_only_event_and_outbox",
        }
        event_ids: list[int] = []
        for gate_id, decision_source in gate_sources.items():
            event_ids.append(self._append_event(
                aggregate_type="action",
                aggregate_id=action_id,
                run_id=run_id,
                action_id=action_id,
                actor=actor,
                event_type="action.output",
                payload={
                    **common,
                    "gate_id": gate_id,
                    "decision": "accepted",
                    "decision_source": decision_source,
                },
                occurred_at=occurred_at,
                causation_id=causation_id,
            ))
        if process.pre_spawn_cancelled:
            gate_g_decision = "not_applicable"
            gate_g_source = "spawn_fence_not_committed"
        elif process.termination_failed:
            gate_g_decision = "rejected"
            gate_g_source = "process_tree_termination_failed"
        elif process.runner_error:
            gate_g_decision = "rejected"
            gate_g_source = "runner_liveness_not_confirmed"
        else:
            gate_g_decision = "accepted"
            gate_g_source = "process_exit_and_tree_cleanup_confirmed"
        event_ids.append(self._append_event(
            aggregate_type="action",
            aggregate_id=action_id,
            run_id=run_id,
            action_id=action_id,
            actor=actor,
            event_type="action.output",
            payload={
                **common,
                "gate_id": "Gate-G",
                "decision": gate_g_decision,
                "decision_source": gate_g_source,
                "exit_code_observed": process.exit_code is not None,
                "termination_failed": process.termination_failed,
            },
            occurred_at=occurred_at,
            causation_id=causation_id,
        ))
        return tuple(event_ids)

    def _settle_terminal_run_after_process(
        self,
        *,
        run_id: str,
        action_id: str,
        actor: ActorRef,
        process: LockedProcessResult,
        receipt_result: str,
        occurred_at: str,
        causation_id: str | None,
    ) -> int:
        run = self.connection.execute(
            "SELECT state, result_json FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise LockedExecutorError("E_RUN_NOT_FOUND", "Run disappeared during execution")
        remaining = int(self.connection.execute(
            "SELECT COUNT(*) FROM actions WHERE run_id = ? "
            "AND state IN ('proposed', 'waiting_approval', 'authorized', 'running')",
            (run_id,),
        ).fetchone()[0])
        if remaining != 0:
            raise LockedExecutorError(
                "E_RUN_TERMINAL_ACTIONS_PENDING",
                "Single-action locked Run still has non-terminal Actions",
            )
        try:
            run_result = json.loads(str(run["result_json"] or "{}"))
        except json.JSONDecodeError:
            run_result = {}
        cancel_pending = (
            str(run["state"]) == "paused"
            and run_result.get("reason") == "cancel_requested"
        )
        if process.pre_spawn_cancelled:
            next_state, event_type, reason = (
                "cancelled", "run.cancelled", "cancelled_before_process_start"
            )
        elif process.termination_failed:
            next_state, event_type, reason = (
                "orphaned", "run.orphaned", "process_tree_termination_failed"
            )
        elif process.cancelled and cancel_pending:
            next_state, event_type, reason = (
                "cancelled", "run.cancelled", "cancelled_after_process_stop"
            )
        elif receipt_result == "effect_unknown":
            next_state, event_type, reason = (
                "orphaned", "run.orphaned", "effect_unknown"
            )
        elif receipt_result == "timed_out":
            next_state, event_type, reason = (
                "timed_out", "run.timed_out", "timeout"
            )
        elif receipt_result == "succeeded":
            next_state, event_type, reason = (
                "succeeded", "run.succeeded", "exit_zero"
            )
        elif receipt_result == "failed":
            next_state, event_type, reason = (
                "failed", "run.failed", "exit_nonzero"
            )
        elif receipt_result == "cancelled":
            next_state, event_type, reason = (
                "cancelled", "run.cancelled", "cancelled"
            )
        else:
            raise LockedExecutorError(
                "E_RUN_RESULT_INVALID",
                "Locked completion produced an unsupported Run result",
            )
        updated = self.connection.execute(
            "UPDATE runs SET state = ?, finished_at = ?, result_json = ? "
            "WHERE id = ? AND state IN ('running', 'paused')",
            (
                next_state,
                occurred_at,
                _json({"state": next_state, "result": receipt_result, "reason": reason}),
                run_id,
            ),
        )
        if updated.rowcount != 1:
            raise LockedExecutorError(
                "E_RUN_SETTLE_RACE",
                "Run changed before terminal locked settlement",
            )
        return self._append_event(
            aggregate_type="run",
            aggregate_id=run_id,
            run_id=run_id,
            action_id=action_id,
            actor=actor,
            event_type=event_type,
            payload={
                "run_id": run_id,
                "state": next_state,
                "result": receipt_result,
                "reason": reason,
            },
            occurred_at=occurred_at,
            causation_id=causation_id,
        )

    def _settle_run_after_process(
        self,
        *,
        run_id: str,
        action_id: str,
        actor: ActorRef,
        process: LockedProcessResult,
        occurred_at: str,
        causation_id: str | None,
    ) -> int | None:
        run = self.connection.execute(
            "SELECT state, result_json FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise LockedExecutorError("E_RUN_NOT_FOUND", "Run disappeared during execution")
        remaining = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM actions WHERE run_id = ? AND state = 'running'",
                (run_id,),
            ).fetchone()[0]
        )
        if remaining > 0:
            return None
        run_state = str(run["state"])
        try:
            run_result = json.loads(str(run["result_json"] or "{}"))
        except json.JSONDecodeError:
            run_result = {}
        cancel_pending = (
            run_state == "paused" and run_result.get("reason") == "cancel_requested"
        )
        if not cancel_pending and not process.termination_failed:
            return None
        next_state = "orphaned" if process.termination_failed else "cancelled"
        event_type = "run.orphaned" if process.termination_failed else "run.cancelled"
        reason = (
            "process_tree_termination_failed"
            if process.termination_failed
            else "cancelled_after_process_stop"
        )
        updated = self.connection.execute(
            """
            UPDATE runs
            SET state = ?, finished_at = ?, result_json = ?
            WHERE id = ? AND state IN ('running', 'paused')
            """,
            (next_state, occurred_at, _json({"state": next_state, "reason": reason}), run_id),
        )
        if updated.rowcount != 1:
            raise LockedExecutorError(
                "E_RUN_SETTLE_RACE",
                "Run changed before process settlement",
            )
        return self._append_event(
            aggregate_type="run",
            aggregate_id=run_id,
            run_id=run_id,
            action_id=action_id,
            actor=actor,
            event_type=event_type,
            payload={"run_id": run_id, "state": next_state, "reason": reason},
            occurred_at=occurred_at,
            causation_id=causation_id,
        )

    def _authorization_provenance(
        self,
        authorization_ref: str,
    ) -> tuple[AuthorizationSource, dict[str, object] | None, str | None]:
        if authorization_ref.startswith("policy_grant:"):
            return AuthorizationSource.POLICY_GRANT, None, None
        if authorization_ref.startswith("approval:"):
            approval_id = authorization_ref.removeprefix("approval:")
            row = self.connection.execute(
                "SELECT decided_by_json, decided_at FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
            if row is None or row["decided_by_json"] is None or row["decided_at"] is None:
                raise LockedExecutorError(
                    "E_APPROVAL_PROVENANCE",
                    "Approval receipt requires decided_by and decided_at",
                )
            return (
                AuthorizationSource.APPROVAL,
                json.loads(str(row["decided_by_json"])),
                str(row["decided_at"]),
            )
        raise LockedExecutorError(
            "E_AUTHORIZATION_SOURCE",
            "Locked executor cannot infer authorization source",
        )

    def _append_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        run_id: str,
        action_id: str,
        actor: ActorRef,
        event_type: str,
        payload: object,
        occurred_at: str,
        causation_id: str | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version,
                run_id, run_seq, action_id, actor_json, causation_id,
                type, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aggregate_type,
                aggregate_id,
                self._next_aggregate_version(aggregate_type, aggregate_id),
                run_id,
                self._next_run_seq(run_id),
                action_id,
                _json(actor.model_dump(mode="json")),
                causation_id,
                event_type,
                _json(payload),
                occurred_at,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event_id,))
        return event_id

    def _next_aggregate_version(self, aggregate_type: str, aggregate_id: str) -> int:
        return int(
            self.connection.execute(
                """
                SELECT COALESCE(MAX(aggregate_version), 0)
                FROM events
                WHERE aggregate_type = ? AND aggregate_id = ?
                """,
                (aggregate_type, aggregate_id),
            ).fetchone()[0]
        ) + 1

    def _next_run_seq(self, run_id: str) -> int:
        return int(
            self.connection.execute(
                """
                SELECT COALESCE(MAX(run_seq), 0)
                FROM events
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()[0]
        ) + 1

    def _transaction(self):
        return _transaction(self.connection)


def default_locked_unittest_runner(
    test_id: str,
    workspace_root: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    cancel_requested: Callable[[], bool] = lambda: False,
) -> LockedProcessResult:
    """Run frozen unittest through argv, never shell=True, with an empty env."""

    result = _run_locked_worker(
        [test_id],
        workspace_root,
        timeout_seconds,
        max_output_bytes,
        cancel_requested,
        getattr(cancel_requested, "pause_requested", lambda: False),
    )
    return _apply_worker_effect_report(result)


def _run_locked_worker(
    worker_args: list[str],
    workspace_root: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    cancel_requested: Callable[[], bool] = lambda: False,
    pause_requested: Callable[[], bool] = lambda: False,
) -> LockedProcessResult:
    """Run the trusted worker with shared output, timeout, and cancellation caps."""

    start = time.monotonic()
    creationflags = 0
    popen_kwargs: dict[str, object] = {"start_new_session": os.name != "nt"}
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | WINDOWS_CREATE_SUSPENDED
        )
        popen_kwargs = {}
    process: subprocess.Popen[bytes] | None = None
    windows_job: WindowsJob | None = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "nana_sidecar.locked_unittest_worker",
                *worker_args,
            ],
            cwd=str(workspace_root),
            env={},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creationflags,
            **popen_kwargs,
        )
        windows_job = WindowsJob.assign(process)
        if os.name == "nt" and windows_job is None:
            raise RuntimeError("Windows worker did not receive a Job Object")
        if windows_job is not None:
            setattr(process, "_nana_windows_job", windows_job)
            windows_job.resume(process)
    except Exception:
        if process is not None:
            try:
                if process.poll() is None:
                    terminated = (
                        windows_job is not None and windows_job.terminate(process)
                    )
                    if not terminated:
                        process.kill()
                        process.wait(timeout=5)
            except Exception:
                pass
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        if windows_job is not None:
            windows_job.close()
        raise
    stdout = bytearray()
    stderr = bytearray()
    exceeded = threading.Event()
    termination_failed = threading.Event()
    output_lock = threading.Lock()

    def read_stream(stream, sink: bytearray) -> None:
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                should_terminate = False
                with output_lock:
                    remaining = max_output_bytes - (len(stdout) + len(stderr))
                    if remaining > 0:
                        sink.extend(chunk[:remaining])
                    if len(chunk) > max(remaining, 0):
                        if not exceeded.is_set():
                            exceeded.set()
                            should_terminate = True
                if should_terminate and not _terminate_process_tree(process):
                    termination_failed.set()
                if exceeded.is_set():
                    break
        finally:
            try:
                stream.close()
            except Exception:
                pass

    threads = [
        threading.Thread(target=read_stream, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=read_stream, args=(process.stderr, stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    cancelled = False
    deadline = start + timeout_seconds
    process_paused = False
    paused_at = 0.0
    while process.poll() is None:
        try:
            should_cancel = cancel_requested()
        except Exception:
            should_cancel = True
            termination_failed.set()
        if should_cancel:
            cancelled = True
            if not _terminate_process_tree(process):
                termination_failed.set()
            break
        try:
            should_pause = pause_requested()
        except Exception:
            should_pause = False
            termination_failed.set()
            if not _terminate_process_tree(process):
                termination_failed.set()
            break
        if should_pause != process_paused:
            try:
                if os.name == "nt":
                    if windows_job is None:
                        raise RuntimeError("Windows worker lost its Job Object")
                    if should_pause:
                        windows_job.suspend(process)
                    else:
                        windows_job.resume_running(process)
                else:
                    os.killpg(process.pid, signal.SIGSTOP if should_pause else signal.SIGCONT)
                if should_pause:
                    paused_at = time.monotonic()
                else:
                    deadline += time.monotonic() - paused_at
                process_paused = should_pause
            except Exception:
                termination_failed.set()
                if not _terminate_process_tree(process):
                    termination_failed.set()
                break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            if not _terminate_process_tree(process):
                termination_failed.set()
            break
        try:
            process.wait(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            continue
    if process.poll() is None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            termination_failed.set()
    for thread in threads:
        thread.join(timeout=5)
    if any(thread.is_alive() for thread in threads):
        termination_failed.set()
    wall_clock_ms = int((time.monotonic() - start) * 1000)
    if windows_job is not None and not windows_job.close():
        termination_failed.set()
    result = LockedProcessResult(
        exit_code=process.returncode,
        stdout=bytes(stdout),
        stderr=bytes(stderr),
        wall_clock_ms=wall_clock_ms,
        timed_out=timed_out,
        output_truncated=exceeded.is_set(),
        cancelled=cancelled,
        termination_failed=termination_failed.is_set(),
    )
    return result


_EFFECT_REPORT_PREFIX = b"NANA_LOCKED_EFFECTS:"


def _apply_worker_effect_report(result: LockedProcessResult) -> LockedProcessResult:
    """Extract the worker's observed logical effects from its framed stderr report."""

    marker = result.stderr.rfind(_EFFECT_REPORT_PREFIX)
    process_only = EffectScope(processes=("builtin:python.unittest.locked",))
    if marker < 0:
        incomplete_execution = (
            result.timed_out
            or result.cancelled
            or result.output_truncated
            or result.termination_failed
        )
        return replace(
            result,
            runner_error=result.runner_error or not incomplete_execution,
            actual_effects=process_only,
        )
    report_start = marker + len(_EFFECT_REPORT_PREFIX)
    report_end = result.stderr.find(b"\n", report_start)
    if report_end < 0:
        report_end = len(result.stderr)
    try:
        report = json.loads(result.stderr[report_start:report_end].decode("utf-8"))
        observed = EffectScope.model_validate(report)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return replace(result, runner_error=True, actual_effects=process_only)
    actual_effects = EffectScope(
        reads=observed.reads,
        writes=observed.writes,
        network=observed.network,
        processes=tuple(
            dict.fromkeys(
                observed.processes + ("builtin:python.unittest.locked",)
            )
        ),
    )
    clean_stderr = result.stderr[:marker] + result.stderr[report_end + 1 :]
    return replace(result, stderr=clean_stderr, actual_effects=actual_effects)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> bool:
    if process.poll() is not None:
        return True
    windows_job = getattr(process, "_nana_windows_job", None)
    job_termination_failed = False
    if windows_job is not None:
        if windows_job.terminate(process):
            return True
        job_termination_failed = True
    windows_tree_unverified = False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    return False
                return process.poll() is not None
            windows_tree_unverified = True
        except Exception:
            windows_tree_unverified = True
    elif process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            return process.poll() is not None
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        process.kill()
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        return process.poll() is not None
    if windows_tree_unverified or job_termination_failed:
        return False
    return process.poll() is not None


def _canonical_json_hash(value: object) -> str:
    return f"sha256:{hashlib.sha256(_json(value).encode('utf-8')).hexdigest()}"


def _transaction(connection: sqlite3.Connection):
    class _Transaction:
        def __enter__(self):
            connection.execute("BEGIN IMMEDIATE")
            return None

        def __exit__(self, exc_type, exc, traceback):
            if exc_type is None:
                connection.commit()
            else:
                if connection.in_transaction:
                    connection.rollback()
            return False

    return _Transaction()
