"""Structured error envelope shared by sidecar and UI."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from nana_sidecar.contracts.common import ContractModel, JsonObject


class ErrorCategory(StrEnum):
    INPUT = "input"
    CONFLICT = "conflict"
    PERMISSION = "permission"
    POLICY = "policy"
    BUDGET = "budget"
    NETWORK = "network"
    PARSER = "parser"
    TOOL = "tool"
    ENVIRONMENT = "environment"
    STORAGE = "storage"
    INTERNAL = "internal"


class ErrorCode(StrEnum):
    VALIDATION = "E_VALIDATION"
    STATE_TRANSITION = "E_STATE_TRANSITION"
    REVISION_CONFLICT = "E_REVISION_CONFLICT"
    COMMAND_REPLAY_CONFLICT = "E_COMMAND_REPLAY_CONFLICT"
    CAPABILITY_UNKNOWN = "E_CAPABILITY_UNKNOWN"
    POLICY_DENIED = "E_POLICY_DENIED"
    BUDGET_EXCEEDED = "E_BUDGET_EXCEEDED"
    APPROVAL_INVALID = "E_APPROVAL_INVALID"
    APPROVAL_EXPIRED = "E_APPROVAL_EXPIRED"
    ACTION_HASH_MISMATCH = "E_ACTION_HASH_MISMATCH"
    LOCATOR_INVALID = "E_LOCATOR_INVALID"
    RELATION_UNKNOWN = "E_REL_UNKNOWN"
    RELATION_INVALID = "E_REL_INVALID"
    SCHEMA_TOO_NEW = "E_SCHEMA_TOO_NEW"
    SCHEMA_INCOMPATIBLE = "E_SCHEMA_INCOMPATIBLE"
    ARTIFACT_UNAVAILABLE = "E_ARTIFACT_UNAVAILABLE"
    INTERNAL = "E_INTERNAL"


class StructuredError(ContractModel):
    code: ErrorCode
    category: ErrorCategory
    message: str
    retryable: bool
    details: JsonObject = Field(default_factory=dict)
    data_safe: bool
    suggested_actions: tuple[str, ...] = ()


class ErrorResponse(ContractModel):
    error: StructuredError
