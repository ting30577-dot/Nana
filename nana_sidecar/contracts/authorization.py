"""Deterministic authorization primitives for D0 contract verification.

This module decides only whether immutable data matches an authorization
contract.  It does not execute an Action, consume a grant, or write state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from nana_sidecar.contracts.capabilities import (
    CapabilityAuthorizationMode,
    CapabilityProviderMode,
    CapabilityRegistryEntry,
    NEVER_GRANT_CAPABILITY_IDS,
)
from nana_sidecar.contracts.common import (
    BudgetSnapshot,
    CapabilityRef,
    ContractModel,
    DataClass,
    EffectScope,
    HashDigest,
    JsonObject,
    RiskTier,
    normalize_utc_datetime,
)
from nana_sidecar.contracts.domain import (
    Approval,
    ApprovalDecision,
    PolicyGrant,
    PolicyGrantState,
)
from nana_sidecar.contracts.safe_json_schema import safe_schema_matches


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON data once, with stable ordering and no ambient defaults."""

    if isinstance(value, ContractModel):
        value = value.model_dump(mode="json", exclude_none=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


class ActionHashMaterial(ContractModel):
    """Every mutable input whose change must invalidate an Approval."""

    capability: CapabilityRef
    args: JsonObject
    args_hash: HashDigest
    data_class: DataClass
    provider: str | None = Field(default=None, min_length=1, max_length=240)
    requested_effects: EffectScope
    network_methods: tuple[str, ...] = ()
    budget: BudgetSnapshot
    risk_tier: RiskTier
    reversible: bool

    @model_validator(mode="after")
    def args_are_canonical(self) -> "ActionHashMaterial":
        if self.args_hash != canonical_json_hash(self.args):
            raise ValueError("args_hash must match canonical args")
        return self


class GrantMatchContext(ContractModel):
    """State supplied by the policy engine without defining runtime accounting."""

    project_id: UUID
    projected_cumulative_budget: BudgetSnapshot
    current_concurrency: int = Field(ge=0)


class AuthorizationMatch(ContractModel):
    matches: bool
    reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def result_matches_reasons(self) -> "AuthorizationMatch":
        if self.matches == bool(self.reasons):
            raise ValueError("matches must be true exactly when reasons is empty")
        return self


def compute_action_hash(material: ActionHashMaterial) -> str:
    """Hash the complete normalized Action authorization surface."""

    return canonical_json_hash(material)


def approval_authorizes(
    approval: Approval,
    *,
    action_id: UUID,
    material: ActionHashMaterial,
    registry_entry: CapabilityRegistryEntry,
    at: datetime,
    prior_uses: int,
) -> AuthorizationMatch:
    reasons: list[str] = []
    checked_at: datetime | None
    try:
        checked_at = normalize_utc_datetime(at)
    except ValueError:
        checked_at = None
        reasons.append("at_not_utc")
    action_hash = compute_action_hash(material)

    reasons.extend(_registry_reasons(registry_entry, material))
    if approval.subject_type != "action":
        reasons.append("subject_type")
    if approval.subject_id != action_id:
        reasons.append("subject_id")
    if approval.subject_hash != action_hash:
        reasons.append("action_hash")
    if approval.decision is not ApprovalDecision.APPROVED:
        reasons.append("decision")
    if checked_at is not None and checked_at >= approval.expires_at:
        reasons.append("expired")
    if prior_uses < 0 or prior_uses >= approval.allowed_uses:
        reasons.append("uses")
    if approval.capability != material.capability:
        reasons.append("capability")
    if approval.requested_effects != material.requested_effects:
        reasons.append("effects")
    if approval.data_class is not material.data_class:
        reasons.append("data_class")
    if approval.provider != material.provider:
        reasons.append("provider")
    if approval.budget != material.budget:
        reasons.append("budget")
    if approval.risk_tier is not material.risk_tier:
        reasons.append("risk_tier")
    if approval.reversible != material.reversible:
        reasons.append("reversible")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return AuthorizationMatch(
        matches=not unique_reasons,
        reasons=unique_reasons,
    )


def policy_grant_matches(
    grant: PolicyGrant,
    *,
    material: ActionHashMaterial,
    registry_entry: CapabilityRegistryEntry,
    context: GrantMatchContext,
    at: datetime,
) -> AuthorizationMatch:
    reasons: list[str] = []
    checked_at: datetime | None
    try:
        checked_at = normalize_utc_datetime(at)
    except ValueError:
        checked_at = None
        reasons.append("at_not_utc")
    constraints = grant.constraints

    reasons.extend(_registry_reasons(registry_entry, material))
    if material.capability.id in NEVER_GRANT_CAPABILITY_IDS:
        reasons.append("capability_requires_one_time_approval")
    elif not registry_entry.grantable:
        reasons.append("capability_not_grantable")
    elif (
        registry_entry.authorization_mode
        is CapabilityAuthorizationMode.ONE_TIME_APPROVAL
    ):
        reasons.append("capability_requires_one_time_approval")
    if grant.state is not PolicyGrantState.ACTIVE:
        reasons.append("grant_state")
    if context.project_id != grant.project_id:
        reasons.append("project")
    if material.capability != grant.capability:
        reasons.append("capability")
    if checked_at is None or not (
        constraints.valid_from <= checked_at < constraints.expires_at
    ):
        reasons.append("validity_window")
    if grant.uses >= constraints.max_uses:
        reasons.append("uses")
    if context.current_concurrency >= constraints.max_concurrency:
        reasons.append("concurrency")
    if material.data_class not in constraints.allowed_data_classes:
        reasons.append("data_class")
    if material.provider is None and constraints.allowed_providers:
        reasons.append("provider")
    if material.provider is not None and (
        not constraints.allowed_providers
        or material.provider not in constraints.allowed_providers
    ):
        reasons.append("provider")
    if not _schema_matches(constraints.args_schema, material.args):
        reasons.append("args_schema")
    if not _scope_is_subset(material.requested_effects.reads, constraints.read_roots):
        reasons.append("read_scope")
    if not _scope_is_subset(
        material.requested_effects.writes,
        constraints.write_roots,
    ):
        reasons.append("write_scope")
    if not _scope_is_subset(
        material.requested_effects.network,
        constraints.network_targets,
    ):
        reasons.append("network_scope")
    if not _scope_is_subset(
        material.requested_effects.processes,
        constraints.process_targets,
    ):
        reasons.append("process_scope")
    if not _scope_is_subset(
        material.network_methods,
        constraints.network_methods,
    ):
        reasons.append("network_method")
    if not _budget_within(material.budget, constraints.per_action_budget):
        reasons.append("per_action_budget")
    if not _budget_within(
        context.projected_cumulative_budget,
        constraints.cumulative_budget,
    ):
        reasons.append("cumulative_budget")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return AuthorizationMatch(
        matches=not unique_reasons,
        reasons=unique_reasons,
    )


def _scope_is_subset(requested: tuple[str, ...], allowed: tuple[str, ...]) -> bool:
    return set(requested).issubset(allowed)


def _optional_limit_within(
    requested: int | None,
    allowed: int | None,
) -> bool:
    if allowed is None:
        return True
    return requested is not None and requested <= allowed


def _budget_within(
    requested: BudgetSnapshot,
    allowed: BudgetSnapshot,
) -> bool:
    direct_limits = (
        "wall_clock_seconds",
        "max_actions",
        "max_concurrency",
        "max_model_calls",
        "max_model_tokens",
        "max_cost_micros",
        "max_retries",
        "max_output_bytes",
        "max_artifact_bytes",
        "max_download_bytes",
    )
    optional_limits = ("cpu_seconds", "memory_bytes", "gpu_seconds")
    if any(
        getattr(requested, name) > getattr(allowed, name)
        for name in direct_limits
    ):
        return False
    if any(
        not _optional_limit_within(
            getattr(requested, name),
            getattr(allowed, name),
        )
        for name in optional_limits
    ):
        return False
    return (
        _scope_is_subset(requested.network_targets, allowed.network_targets)
        and _scope_is_subset(requested.read_roots, allowed.read_roots)
        and _scope_is_subset(requested.write_roots, allowed.write_roots)
    )


def _registry_reasons(
    registry_entry: CapabilityRegistryEntry,
    material: ActionHashMaterial,
) -> list[str]:
    reasons: list[str] = []
    if registry_entry.capability != material.capability:
        reasons.append("capability_registry")
    if registry_entry.risk_tier is not material.risk_tier:
        reasons.append("capability_registry_risk")
    if registry_entry.reversible != material.reversible:
        reasons.append("capability_registry_reversible")
    if not safe_schema_matches(registry_entry.args_schema, material.args):
        reasons.append("capability_registry_args")
    if not _scope_is_subset(material.requested_effects.reads, registry_entry.read_roots):
        reasons.append("capability_registry_read_scope")
    if not _scope_is_subset(
        material.requested_effects.writes,
        registry_entry.write_roots,
    ):
        reasons.append("capability_registry_write_scope")
    if not _scope_is_subset(
        material.requested_effects.network,
        registry_entry.network_targets,
    ):
        reasons.append("capability_registry_network_scope")
    if not _scope_is_subset(
        material.network_methods,
        registry_entry.network_methods,
    ):
        reasons.append("capability_registry_network_method")
    if not _scope_is_subset(
        material.requested_effects.processes,
        registry_entry.process_targets,
    ):
        reasons.append("capability_registry_process_scope")
    if (
        registry_entry.timeout_seconds is not None
        and material.budget.wall_clock_seconds > registry_entry.timeout_seconds
    ):
        reasons.append("capability_registry_timeout")
    if registry_entry.provider_mode is CapabilityProviderMode.FORBIDDEN:
        if material.provider is not None:
            reasons.append("provider")
    elif registry_entry.provider_mode is CapabilityProviderMode.REQUIRED:
        if material.provider is None:
            reasons.append("provider")
    if material.provider is not None and (
        not registry_entry.allowed_providers
        or material.provider not in registry_entry.allowed_providers
    ):
        reasons.append("provider")
    return reasons


def _schema_matches(schema: JsonObject, value: Any) -> bool:
    """Validate the documented safe JSON-Schema subset; unknown keys deny."""

    return safe_schema_matches(schema, value)
