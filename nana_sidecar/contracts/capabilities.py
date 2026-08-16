"""Closed Capability Registry contracts for executable D2 work."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from nana_sidecar.contracts.common import (
    CapabilityRef,
    ContractModel,
    HashDigest,
    JsonObject,
    RiskTier,
)
from nana_sidecar.contracts.safe_json_schema import validate_safe_json_schema


NEVER_GRANT_CAPABILITY_IDS = frozenset(
    {
        "decision.confirm",
        "export.draft_external",
        "export.publish",
        "object.delete",
    }
)


class CapabilityAuthorizationMode(StrEnum):
    AUTO_POLICY = "auto_policy"
    POLICY_GRANT = "policy_grant"
    ONE_TIME_APPROVAL = "one_time_approval"


class CapabilityProviderMode(StrEnum):
    FORBIDDEN = "forbidden"
    OPTIONAL = "optional"
    REQUIRED = "required"


class CapabilityDefaultEffect(StrEnum):
    REVERSIBLE = "reversible"
    EFFECT_UNKNOWN = "effect_unknown"


def capability_registry_contract_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _plain_json(value: Any) -> Any:
    if isinstance(value, ContractModel):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    if isinstance(value, list):
        return [_plain_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain_json(item) for key, item in value.items()}
    return value


class CapabilityRegistryEntry(ContractModel):
    """Registry truth for a pinned executable Capability implementation."""

    capability: CapabilityRef
    args_schema: JsonObject
    risk_tier: RiskTier
    reversible: bool
    authorization_mode: CapabilityAuthorizationMode
    grantable: bool
    provider_mode: CapabilityProviderMode = CapabilityProviderMode.FORBIDDEN
    allowed_providers: tuple[str, ...] = ()
    read_roots: tuple[str, ...] = ()
    write_roots: tuple[str, ...] = ()
    network_targets: tuple[str, ...] = ()
    network_methods: tuple[str, ...] = ()
    env_keys: tuple[str, ...] = ()
    process_targets: tuple[str, ...] = ()
    timeout_seconds: int | None = Field(default=None, gt=0)
    default_effect: CapabilityDefaultEffect = CapabilityDefaultEffect.EFFECT_UNKNOWN
    contract_digest: HashDigest | None = Field(default=None)

    @model_validator(mode="after")
    def validate_registry_entry(self) -> "CapabilityRegistryEntry":
        validate_safe_json_schema(self.args_schema)
        for field_name in (
            "allowed_providers",
            "read_roots",
            "write_roots",
            "network_targets",
            "network_methods",
            "env_keys",
            "process_targets",
        ):
            if any(not item.strip() for item in getattr(self, field_name)):
                raise ValueError(f"{field_name} cannot contain blank entries")
        if self.provider_mode is CapabilityProviderMode.FORBIDDEN:
            if self.allowed_providers:
                raise ValueError("forbidden provider mode cannot allow providers")
        elif self.provider_mode is CapabilityProviderMode.REQUIRED:
            if not self.allowed_providers:
                raise ValueError("required provider mode needs an allowlist")
        if self.capability.id in NEVER_GRANT_CAPABILITY_IDS:
            if self.grantable:
                raise ValueError("absolute-approval capabilities cannot be grantable")
            if (
                self.authorization_mode
                is not CapabilityAuthorizationMode.ONE_TIME_APPROVAL
            ):
                raise ValueError(
                    "absolute-approval capabilities require one-time approval"
                )
        material = self.model_dump(
            mode="json",
            exclude={"contract_digest"},
        )
        expected = capability_registry_contract_digest(material)
        if self.contract_digest != expected:
            raise ValueError("capability registry contract_digest mismatch")
        return self

    @model_validator(mode="before")
    @classmethod
    def fill_contract_digest(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = dict(data)
        for name, field in cls.model_fields.items():
            if name == "contract_digest" or name in raw:
                continue
            if field.is_required():
                continue
            raw[name] = field.default
        material = {
            key: _plain_json(value)
            for key, value in raw.items()
            if key != "contract_digest"
        }
        if raw.get("contract_digest") is None:
            raw["contract_digest"] = capability_registry_contract_digest(material)
        return raw
