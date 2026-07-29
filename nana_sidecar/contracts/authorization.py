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

from nana_sidecar.contracts.common import (
    BudgetSnapshot,
    ContractModel,
    DataClass,
    EffectScope,
    HashDigest,
    JsonObject,
    RiskTier,
    VersionedRef,
)
from nana_sidecar.contracts.domain import (
    Approval,
    ApprovalDecision,
    PolicyGrant,
    PolicyGrantState,
)


NEVER_GRANT_CAPABILITIES = frozenset(
    {"decision.confirm", "export.publish", "object.delete"}
)

_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "type",
        "required",
        "properties",
        "additionalProperties",
        "const",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "items",
        "minItems",
        "maxItems",
    }
)


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

    capability: VersionedRef
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
    at: datetime,
    prior_uses: int,
) -> AuthorizationMatch:
    reasons: list[str] = []
    action_hash = compute_action_hash(material)

    if approval.subject_type != "action":
        reasons.append("subject_type")
    if approval.subject_id != action_id:
        reasons.append("subject_id")
    if approval.subject_hash != action_hash:
        reasons.append("action_hash")
    if approval.decision is not ApprovalDecision.APPROVED:
        reasons.append("decision")
    if at >= approval.expires_at:
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
    context: GrantMatchContext,
    at: datetime,
) -> AuthorizationMatch:
    reasons: list[str] = []
    constraints = grant.constraints

    if material.capability.id in NEVER_GRANT_CAPABILITIES:
        reasons.append("capability_requires_one_time_approval")
    if grant.state is not PolicyGrantState.ACTIVE:
        reasons.append("grant_state")
    if context.project_id != grant.project_id:
        reasons.append("project")
    if material.capability != grant.capability:
        reasons.append("capability")
    if not (constraints.valid_from <= at < constraints.expires_at):
        reasons.append("validity_window")
    if grant.uses >= constraints.max_uses:
        reasons.append("uses")
    if context.current_concurrency >= constraints.max_concurrency:
        reasons.append("concurrency")
    if material.data_class not in constraints.allowed_data_classes:
        reasons.append("data_class")
    if material.provider is not None and (
        material.provider not in constraints.allowed_providers
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
    if material.requested_effects.processes:
        reasons.append("process_scope_not_grantable")
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


def _schema_matches(schema: JsonObject, value: Any) -> bool:
    """Validate the documented safe JSON-Schema subset; unknown keys deny."""

    if not set(schema).issubset(_SUPPORTED_SCHEMA_KEYS):
        return False
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            return False
        if not set(required).issubset(value):
            return False
        additional = schema.get("additionalProperties", False)
        if additional not in (True, False):
            return False
        if not additional and not set(value).issubset(properties):
            return False
        return all(
            key not in value
            or (
                isinstance(child_schema, dict)
                and _schema_matches(child_schema, value[key])
            )
            for key, child_schema in properties.items()
        )
    if expected_type == "array":
        if not isinstance(value, list):
            return False
        if not _length_matches(schema, value):
            return False
        item_schema = schema.get("items", {})
        return isinstance(item_schema, dict) and all(
            _schema_matches(item_schema, item) for item in value
        )
    if expected_type == "string":
        return isinstance(value, str) and _length_matches(schema, value)
    if expected_type == "integer":
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and _number_matches(schema, value)
        )
    if expected_type == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and _number_matches(schema, value)
        )
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return expected_type is None


def _length_matches(schema: JsonObject, value: Any) -> bool:
    minimum = schema.get("minLength", schema.get("minItems"))
    maximum = schema.get("maxLength", schema.get("maxItems"))
    return (
        (minimum is None or len(value) >= minimum)
        and (maximum is None or len(value) <= maximum)
    )


def _number_matches(schema: JsonObject, value: int | float) -> bool:
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    return (
        (minimum is None or value >= minimum)
        and (maximum is None or value <= maximum)
    )
