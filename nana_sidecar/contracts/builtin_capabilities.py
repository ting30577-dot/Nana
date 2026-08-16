"""Built-in executable Capability registry entries for dev runtime slices."""

from __future__ import annotations

import hashlib

from nana_sidecar.contracts.capabilities import (
    CapabilityAuthorizationMode,
    CapabilityDefaultEffect,
    CapabilityProviderMode,
    CapabilityRegistryEntry,
)
from nana_sidecar.contracts.common import CapabilityRef


PYTHON_UNITTEST_LOCKED_TEST_IDS = (
    "tests.test_sliding_window.VariableWindowTests."
    "test_finds_shortest_matching_window",
)


def _digest(material: str) -> str:
    return f"sha256:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


PYTHON_UNITTEST_LOCKED_CAPABILITY = CapabilityRef(
    id="python.unittest.locked",
    version="1",
    digest=_digest(
        "python.unittest.locked:v1:"
        + "\n".join(PYTHON_UNITTEST_LOCKED_TEST_IDS)
    ),
)


DRAFT_EXPORT_FILENAME = "NANA_DRAFT_REPORT.md"
DRAFT_EXPORT_MEDIA_TYPE = "text/markdown"
DRAFT_EXPORT_MAX_BYTES = 4096
EXPORT_DRAFT_EXTERNAL_CAPABILITY = CapabilityRef(
    id="export.draft_external",
    version="1",
    digest=_digest(
        "export.draft_external:v1:"
        f"{DRAFT_EXPORT_FILENAME}:{DRAFT_EXPORT_MEDIA_TYPE}:"
        f"{DRAFT_EXPORT_MAX_BYTES}:atomic-no-overwrite"
    ),
)


def python_unittest_locked_registry_entry() -> CapabilityRegistryEntry:
    """Return the first locked dev Capability declared by ADR-005."""

    return CapabilityRegistryEntry(
        capability=PYTHON_UNITTEST_LOCKED_CAPABILITY,
        args_schema={
            "type": "object",
            "required": ["test_id"],
            "properties": {
                "test_id": {
                    "type": "string",
                    "enum": list(PYTHON_UNITTEST_LOCKED_TEST_IDS),
                },
            },
            "additionalProperties": False,
        },
        risk_tier="T2",
        reversible=True,
        authorization_mode=CapabilityAuthorizationMode.POLICY_GRANT,
        grantable=True,
        provider_mode=CapabilityProviderMode.FORBIDDEN,
        allowed_providers=(),
        read_roots=("project:source", "project:tests"),
        write_roots=(),
        network_targets=(),
        network_methods=(),
        env_keys=(),
        process_targets=("builtin:python.unittest.locked",),
        timeout_seconds=60,
        default_effect=CapabilityDefaultEffect.REVERSIBLE,
    )


def export_draft_external_registry_entry() -> CapabilityRegistryEntry:
    """Return the exact one-time T3 local draft-export capability."""

    string_digest = {"type": "string", "minLength": 71, "maxLength": 71}
    identifier = {"type": "string", "minLength": 36, "maxLength": 36}
    return CapabilityRegistryEntry(
        capability=EXPORT_DRAFT_EXTERNAL_CAPABILITY,
        args_schema={
            "type": "object",
            "required": [
                "draft_artifact_id",
                "draft_hash",
                "renderer_digest",
                "selection_identity_digest",
                "target_commitment",
                "filename",
                "media_type",
                "size",
            ],
            "properties": {
                "draft_artifact_id": identifier,
                "draft_hash": string_digest,
                "renderer_digest": string_digest,
                "selection_identity_digest": string_digest,
                "target_commitment": string_digest,
                "filename": {"type": "string", "const": DRAFT_EXPORT_FILENAME},
                "media_type": {"type": "string", "const": DRAFT_EXPORT_MEDIA_TYPE},
                "size": {"type": "integer", "minimum": 1, "maximum": DRAFT_EXPORT_MAX_BYTES},
            },
            "additionalProperties": False,
        },
        risk_tier="T3",
        reversible=False,
        authorization_mode=CapabilityAuthorizationMode.ONE_TIME_APPROVAL,
        grantable=False,
        provider_mode=CapabilityProviderMode.FORBIDDEN,
        allowed_providers=(),
        read_roots=("workspace:canonical_public_draft",),
        write_roots=("external:fixed_local_draft_target",),
        network_targets=(),
        network_methods=(),
        env_keys=(),
        process_targets=(),
        timeout_seconds=30,
        default_effect=CapabilityDefaultEffect.EFFECT_UNKNOWN,
    )
