"""D2-03b durable Capability admission transactions.

This module authorizes already-proposed Actions.  It does not claim scheduler
work, spawn processes, run tests, or write ActionReceipts.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator
from uuid import UUID

from nana_sidecar.contracts.authorization import (
    ActionHashMaterial,
    GrantMatchContext,
    approval_authorizes,
    canonical_json_hash,
    compute_action_hash,
    policy_grant_matches,
)
from nana_sidecar.contracts.capabilities import CapabilityRegistryEntry
from nana_sidecar.contracts.common import (
    ActorRef,
    BudgetSnapshot,
    CapabilityRef,
    EffectScope,
)
from nana_sidecar.contracts.domain import (
    Approval,
    PolicyGrant,
)


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class AdmissionStateError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    kind: str
    action_id: str
    authorization_source: str
    authorization_ref: str
    event_ids: tuple[int, ...]


ArgsArtifactLoader = Callable[[sqlite3.Row], bytes]


class CapabilityAdmissionService:
    """Authorize Actions through PolicyGrant or one-time Approval paths."""

    _authorizable_action_states = frozenset({"proposed", "waiting_approval"})

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        now: Callable[[], str],
        load_args_artifact: ArgsArtifactLoader,
    ) -> None:
        self.connection = connection
        self._now = now
        self._load_args_artifact = load_args_artifact

    def authorize_with_policy_grant(
        self,
        *,
        action_id: str,
        grant_id: str,
        material: ActionHashMaterial,
        context: GrantMatchContext,
        actor: ActorRef,
        causation_id: str | None = None,
    ) -> AdmissionResult:
        self._require_idle()
        with self._transaction():
            action = self._require_bound_action(action_id, material)
            self._require_context_bound_to_action(action, context)
            registry_entry = self._require_registry_entry(material.capability)
            grant = self._require_policy_grant(grant_id)
            canonical_context = self._canonical_grant_context(
                action=action,
                grant=grant,
                material=material,
            )
            match = policy_grant_matches(
                grant,
                material=material,
                registry_entry=registry_entry,
                context=canonical_context,
                at=self._now_datetime(),
            )
            if not match.matches:
                raise AdmissionStateError(
                    "E_POLICY_GRANT_DENIED",
                    "PolicyGrant does not authorize this Action: "
                    + ",".join(match.reasons),
                )
            event_id = self._authorize_action(
                action=action,
                material=material,
                actor=actor,
                authorization_source="policy_grant",
                authorization_ref=f"policy_grant:{grant_id}",
                registry_entry=registry_entry,
                causation_id=causation_id,
            )
            self._consume_policy_grant(grant)
            return AdmissionResult(
                kind="authorized",
                action_id=action_id,
                authorization_source="policy_grant",
                authorization_ref=f"policy_grant:{grant_id}",
                event_ids=(event_id,),
            )

    def authorize_with_approval(
        self,
        *,
        action_id: str,
        approval_id: str,
        material: ActionHashMaterial,
        actor: ActorRef,
        causation_id: str | None = None,
    ) -> AdmissionResult:
        self._require_idle()
        with self._transaction():
            return self._authorize_with_approval_in_transaction(
                action_id=action_id,
                approval_id=approval_id,
                material=material,
                actor=actor,
                causation_id=causation_id,
            )

    def _authorize_with_approval_in_transaction(
        self,
        *,
        action_id: str,
        approval_id: str,
        material: ActionHashMaterial,
        actor: ActorRef,
        causation_id: str | None = None,
    ) -> AdmissionResult:
        """Authorize and consume inside the caller's one outer transaction."""

        if not self.connection.in_transaction:
            raise AdmissionStateError(
                "E_TRANSACTION_REQUIRED",
                "in-transaction Approval admission requires an active transaction",
            )
        action = self._require_bound_action(action_id, material)
        registry_entry = self._require_registry_entry(material.capability)
        approval = self._require_approval(approval_id)
        prior_uses = self._approval_use_count(approval_id)
        match = approval_authorizes(
            approval,
            action_id=UUID(action_id),
            material=material,
            registry_entry=registry_entry,
            at=self._now_datetime(),
            prior_uses=prior_uses,
        )
        if not match.matches:
            raise AdmissionStateError(
                "E_APPROVAL_DENIED",
                "Approval does not authorize this Action: "
                + ",".join(match.reasons),
            )
        event_id = self._authorize_action(
            action=action,
            material=material,
            actor=actor,
            authorization_source="approval",
            authorization_ref=f"approval:{approval_id}",
            registry_entry=registry_entry,
            causation_id=causation_id,
        )
        self.connection.execute(
            """
            INSERT INTO approval_consumptions(
                approval_id, action_id, event_id, consumed_at
            ) VALUES (?, ?, ?, ?)
            """,
            (approval_id, action_id, event_id, self._now()),
        )
        return AdmissionResult(
            kind="authorized",
            action_id=action_id,
            authorization_source="approval",
            authorization_ref=f"approval:{approval_id}",
            event_ids=(event_id,),
        )

    def _require_bound_action(
        self,
        action_id: str,
        material: ActionHashMaterial,
    ) -> sqlite3.Row:
        action = self.connection.execute(
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
                runs.project_id AS run_project_id
            FROM actions
            LEFT JOIN runs ON runs.id = actions.run_id
            WHERE actions.id = ?
            """,
            (action_id,),
        ).fetchone()
        if action is None:
            raise AdmissionStateError("E_ACTION_NOT_FOUND", "Action does not exist")
        state = str(action["state"])
        if state not in self._authorizable_action_states:
            raise AdmissionStateError(
                "E_ACTION_NOT_AUTHORIZEABLE",
                f"Action in state {state!r} cannot be authorized",
            )
        if action["run_id"] is None or action["run_project_id"] is None:
            raise AdmissionStateError(
                "E_ACTION_RUN_REQUIRED",
                "Admission requires an Action attached to a Run",
            )
        self._verify_action_material_binding(action, material)
        return action

    def _verify_action_material_binding(
        self,
        action: sqlite3.Row,
        material: ActionHashMaterial,
    ) -> None:
        capability = material.capability
        if (
            str(action["capability_id"]) != capability.id
            or str(action["capability_version"]) != capability.version
            or str(action["executable_digest"]) != capability.digest
        ):
            raise AdmissionStateError(
                "E_ACTION_CAPABILITY_MISMATCH",
                "Action capability does not match authorization material",
            )
        args_artifact = self._require_args_artifact(str(action["args_artifact_id"]))
        raw_args = self._load_args_artifact(args_artifact)
        if len(raw_args) != int(args_artifact["size"]):
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_SIZE",
                "Args Artifact bytes do not match its persisted size",
            )
        if len(raw_args) > material.budget.max_artifact_bytes:
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_BUDGET",
                "Args Artifact exceeds the authorized artifact budget",
            )
        expected_blob_hash = f"sha256:{hashlib.sha256(raw_args).hexdigest()}"
        if expected_blob_hash != str(args_artifact["blob_hash"]):
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_HASH",
                "Args Artifact bytes do not match its blob hash",
            )
        try:
            args = json.loads(raw_args.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_JSON",
                "Args Artifact is not canonical JSON",
            ) from exc
        if not isinstance(args, dict):
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_JSON",
                "Args Artifact must contain a JSON object",
            )
        if args != material.args:
            raise AdmissionStateError(
                "E_ARGS_MATERIAL_MISMATCH",
                "Args Artifact JSON does not match authorization material",
            )
        if canonical_json_hash(args) != material.args_hash:
            raise AdmissionStateError(
                "E_ARGS_HASH_MISMATCH",
                "Args hash does not match canonical Args Artifact JSON",
            )
        if str(action["args_hash"]) != material.args_hash:
            raise AdmissionStateError(
                "E_ACTION_ARGS_HASH_MISMATCH",
                "Persisted Action args_hash does not match material",
            )
        if str(action["action_hash"]) != compute_action_hash(material):
            raise AdmissionStateError(
                "E_ACTION_HASH_MISMATCH",
                "Persisted Action action_hash does not match material",
            )
        if str(action["risk_tier"]) != material.risk_tier.value:
            raise AdmissionStateError(
                "E_ACTION_RISK_MISMATCH",
                "Persisted Action risk_tier does not match material",
            )
        persisted_effects = EffectScope.model_validate_json(
            str(action["requested_effects_json"])
        )
        if persisted_effects != material.requested_effects:
            raise AdmissionStateError(
                "E_ACTION_EFFECTS_MISMATCH",
                "Persisted Action effects do not match material",
            )

    def _require_context_bound_to_action(
        self,
        action: sqlite3.Row,
        context: GrantMatchContext,
    ) -> None:
        if UUID(str(action["run_project_id"])) != context.project_id:
            raise AdmissionStateError(
                "E_CONTEXT_PROJECT_MISMATCH",
                "Grant context project_id does not match Action Run",
            )

    def _canonical_grant_context(
        self,
        *,
        action: sqlite3.Row,
        grant: PolicyGrant,
        material: ActionHashMaterial,
    ) -> GrantMatchContext:
        """Derive grant budget/concurrency facts from append-only authorization rows."""

        authorization_ref = f"policy_grant:{grant.id}"
        rows = self.connection.execute(
            """
            SELECT action_authorizations.material_json
            FROM action_authorizations
            JOIN actions ON actions.id = action_authorizations.action_id
            WHERE action_authorizations.authorization_source = 'policy_grant'
              AND action_authorizations.authorization_ref = ?
            ORDER BY action_authorizations.authorization_event_id
            """,
            (authorization_ref,),
        ).fetchall()
        budgets: list[BudgetSnapshot] = []
        for row in rows:
            try:
                prior_material = ActionHashMaterial.model_validate_json(
                    str(row["material_json"])
                )
            except ValueError as exc:
                raise AdmissionStateError(
                    "E_AUTHORIZATION_MATERIAL_INVALID",
                    "Stored grant authorization material is invalid",
                ) from exc
            budgets.append(prior_material.budget)
        budgets.append(material.budget)
        running = int(
            self.connection.execute(
                """
                SELECT COUNT(*)
                FROM actions
                JOIN action_authorizations
                  ON action_authorizations.action_id = actions.id
                WHERE action_authorizations.authorization_source = 'policy_grant'
                  AND action_authorizations.authorization_ref = ?
                  AND actions.state = 'running'
                """,
                (authorization_ref,),
            ).fetchone()[0]
        )
        return GrantMatchContext(
            project_id=UUID(str(action["run_project_id"])),
            projected_cumulative_budget=_sum_budgets(budgets),
            current_concurrency=running,
        )

    def _require_args_artifact(self, artifact_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT id, media_type, blob_hash, size, state
            FROM artifacts
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_NOT_FOUND",
                "Args Artifact does not exist",
            )
        if str(row["state"]) != "available":
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_UNAVAILABLE",
                "Args Artifact is not available",
            )
        if str(row["media_type"]) != "application/json":
            raise AdmissionStateError(
                "E_ARGS_ARTIFACT_MEDIA_TYPE",
                "Args Artifact must be application/json",
            )
        return row

    def _require_registry_entry(
        self,
        capability: CapabilityRef,
    ) -> CapabilityRegistryEntry:
        row = self.connection.execute(
            """
            SELECT executable_digest, entry_json, contract_digest
            FROM capability_registry_entries
            WHERE capability_id = ?
              AND capability_version = ?
              AND executable_digest = ?
            """,
            (capability.id, capability.version, capability.digest),
        ).fetchone()
        if row is None:
            raise AdmissionStateError(
                "E_CAPABILITY_UNREGISTERED",
                "Capability is not registered with this executable digest",
            )
        entry = CapabilityRegistryEntry.model_validate_json(str(row["entry_json"]))
        if (
            str(row["executable_digest"]) != entry.capability.digest
            or str(row["contract_digest"]) != entry.contract_digest
            or entry.capability != capability
        ):
            raise AdmissionStateError(
                "E_CAPABILITY_REGISTRY_MISMATCH",
                "Persisted registry row is not internally consistent",
            )
        return entry

    def _require_policy_grant(self, grant_id: str) -> PolicyGrant:
        row = self.connection.execute(
            """
            SELECT
                id, project_id, capability_id, capability_version,
                executable_digest, constraints_json, state, uses, created_at
            FROM policy_grants
            WHERE id = ?
            """,
            (grant_id,),
        ).fetchone()
        if row is None:
            raise AdmissionStateError(
                "E_POLICY_GRANT_NOT_FOUND",
                "PolicyGrant does not exist",
            )
        return PolicyGrant(
            id=UUID(str(row["id"])),
            project_id=UUID(str(row["project_id"])),
            capability=CapabilityRef(
                id=str(row["capability_id"]),
                version=str(row["capability_version"]),
                digest=str(row["executable_digest"]),
            ),
            constraints=json.loads(str(row["constraints_json"])),
            state=str(row["state"]),
            uses=int(row["uses"]),
            created_at=str(row["created_at"]),
        )

    def _require_approval(self, approval_id: str) -> Approval:
        row = self.connection.execute(
            """
            SELECT
                id, subject_type, subject_id, subject_hash, capability_json,
                parameter_summary_json, requested_effects_json, data_class,
                provider, budget_json, risk_tier, reversible, allowed_uses,
                expires_at, decision, decided_by_json, decided_at
            FROM approvals
            WHERE id = ?
            """,
            (approval_id,),
        ).fetchone()
        if row is None:
            raise AdmissionStateError(
                "E_APPROVAL_NOT_FOUND",
                "Approval does not exist",
            )
        decided_by = (
            None
            if row["decided_by_json"] is None
            else json.loads(str(row["decided_by_json"]))
        )
        return Approval(
            id=UUID(str(row["id"])),
            subject_type=str(row["subject_type"]),
            subject_id=UUID(str(row["subject_id"])),
            subject_hash=str(row["subject_hash"]),
            capability=json.loads(str(row["capability_json"])),
            parameter_summary=json.loads(str(row["parameter_summary_json"])),
            requested_effects=json.loads(str(row["requested_effects_json"])),
            data_class=str(row["data_class"]),
            provider=row["provider"],
            budget=json.loads(str(row["budget_json"])),
            risk_tier=str(row["risk_tier"]),
            reversible=bool(int(row["reversible"])),
            allowed_uses=int(row["allowed_uses"]),
            expires_at=str(row["expires_at"]),
            decision=str(row["decision"]),
            decided_by=decided_by,
            decided_at=row["decided_at"],
        )

    def _approval_use_count(self, approval_id: str) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()[0]
        )

    def _consume_policy_grant(self, grant: PolicyGrant) -> None:
        next_uses = grant.uses + 1
        next_state = (
            "exhausted"
            if next_uses >= grant.constraints.max_uses
            else grant.state.value
        )
        updated = self.connection.execute(
            """
            UPDATE policy_grants
            SET uses = ?, state = ?
            WHERE id = ? AND uses = ? AND state = 'active'
            """,
            (next_uses, next_state, str(grant.id), grant.uses),
        )
        if updated.rowcount != 1:
            raise AdmissionStateError(
                "E_POLICY_GRANT_CONSUME_RACE",
                "PolicyGrant changed before consumption could be recorded",
            )

    def _authorize_action(
        self,
        *,
        action: sqlite3.Row,
        material: ActionHashMaterial,
        actor: ActorRef,
        authorization_source: str,
        authorization_ref: str,
        registry_entry: CapabilityRegistryEntry,
        causation_id: str | None,
    ) -> int:
        occurred_at = self._now()
        previous_state = str(action["state"])
        next_policy_decision = (
            "grant" if authorization_source == "policy_grant" else "approval_required"
        )
        updated = self.connection.execute(
            """
            UPDATE actions
            SET state = 'authorized',
                authorization_ref = ?,
                policy_decision = ?
            WHERE id = ? AND state = ?
            """,
            (authorization_ref, next_policy_decision, str(action["id"]), previous_state),
        )
        if updated.rowcount != 1:
            raise AdmissionStateError(
                "E_ACTION_AUTHORIZE_RACE",
                "Action changed before authorization could be recorded",
            )
        event_id = self._append_event(
            aggregate_type="action",
            aggregate_id=str(action["id"]),
            run_id=str(action["run_id"]),
            action_id=str(action["id"]),
            actor=actor,
            event_type="action.authorized",
            payload={
                "action_id": str(action["id"]),
                "previous_state": previous_state,
                "state": "authorized",
                "authorization_source": authorization_source,
                "authorization_ref": authorization_ref,
                "authorized_effects": material.requested_effects.model_dump(
                    mode="json"
                ),
            },
            occurred_at=occurred_at,
            causation_id=causation_id,
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
                str(action["id"]),
                compute_action_hash(material),
                material.model_dump_json(),
                registry_entry.contract_digest,
                authorization_source,
                authorization_ref,
                event_id,
                occurred_at,
            ),
        )
        return event_id

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
        causation_id: str | None,
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
        self.connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (event_id,),
        )
        return event_id

    def _next_aggregate_version(
        self,
        aggregate_type: str,
        aggregate_id: str,
    ) -> int:
        current = self.connection.execute(
            """
            SELECT COALESCE(MAX(aggregate_version), 0)
            FROM events
            WHERE aggregate_type = ? AND aggregate_id = ?
            """,
            (aggregate_type, aggregate_id),
        ).fetchone()[0]
        return int(current) + 1

    def _next_run_seq(self, run_id: str) -> int:
        current = self.connection.execute(
            """
            SELECT COALESCE(MAX(run_seq), 0)
            FROM events
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]
        return int(current) + 1

    def _now_datetime(self):
        from datetime import datetime

        return datetime.fromisoformat(self._now().replace("Z", "+00:00"))

    def _require_idle(self) -> None:
        if self.connection.in_transaction:
            raise AdmissionStateError(
                "E_TRANSACTION_ACTIVE",
                "Admission requires an idle SQLite connection",
            )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        else:
            self.connection.commit()


def _sum_optional(values: list[int | None], *, use_max: bool = False) -> int | None:
    if any(value is None for value in values):
        return None
    concrete = [int(value) for value in values if value is not None]
    return max(concrete) if use_max else sum(concrete)


def _ordered_union(values: list[tuple[str, ...]]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in values for item in group))


def _sum_budgets(budgets: list[BudgetSnapshot]) -> BudgetSnapshot:
    if not budgets:
        raise ValueError("at least one budget is required")
    return BudgetSnapshot(
        wall_clock_seconds=sum(item.wall_clock_seconds for item in budgets),
        cpu_seconds=_sum_optional([item.cpu_seconds for item in budgets]),
        memory_bytes=_sum_optional(
            [item.memory_bytes for item in budgets],
            use_max=True,
        ),
        gpu_seconds=_sum_optional([item.gpu_seconds for item in budgets]),
        max_actions=sum(item.max_actions for item in budgets),
        max_concurrency=max(item.max_concurrency for item in budgets),
        max_model_calls=sum(item.max_model_calls for item in budgets),
        max_model_tokens=sum(item.max_model_tokens for item in budgets),
        max_cost_micros=sum(item.max_cost_micros for item in budgets),
        max_retries=sum(item.max_retries for item in budgets),
        max_output_bytes=sum(item.max_output_bytes for item in budgets),
        max_artifact_bytes=sum(item.max_artifact_bytes for item in budgets),
        max_download_bytes=sum(item.max_download_bytes for item in budgets),
        network_targets=_ordered_union([item.network_targets for item in budgets]),
        read_roots=_ordered_union([item.read_roots for item in budgets]),
        write_roots=_ordered_union([item.write_roots for item in budgets]),
    )
