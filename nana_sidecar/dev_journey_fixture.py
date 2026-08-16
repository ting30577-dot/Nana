"""Typed loader for the frozen v0.3.0-dev research journey."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from nana_sidecar.contracts.commands import CommandResult
from nana_sidecar.contracts.common import ActorRef, DataClass
from nana_sidecar.contracts.journey import (
    JourneyCommandRequest,
    WorkspaceBootstrapSpec,
)
from nana_sidecar.storage.journey_commands import (
    FrozenResourceDescriptor,
    JourneyCommandService,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "fixtures" / "v0.3.0-dev" / "d3_journey_commands.json"
_REQUEST_ADAPTER = TypeAdapter(JourneyCommandRequest)


@dataclass(frozen=True, slots=True)
class DevJourneyLoadResult:
    ids: dict[str, UUID]
    command_results: tuple[CommandResult, ...]


def read_dev_journey_definition(path: str | Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("fixture_version") != 1:
        raise ValueError("unsupported D3 journey fixture")
    return value


def workspace_bootstrap_spec(
    definition: dict[str, Any],
) -> WorkspaceBootstrapSpec:
    workspace = definition["workspace"]
    return WorkspaceBootstrapSpec(
        workspace_id=workspace["id"],
        data_root=workspace["data_root"],
        policy=workspace["policy"],
        created_at=definition["created_at"],
    )


def frozen_resource_descriptor(
    definition: dict[str, Any],
    *,
    read_root: str | Path = ROOT,
) -> FrozenResourceDescriptor:
    resource = definition["resource"]
    return FrozenResourceDescriptor(
        descriptor_id=resource["descriptor_id"],
        read_root=Path(read_root),
        logical_ref=resource["logical_ref"],
        media_type=resource["media_type"],
        data_class=DataClass(resource["data_class"]),
        license=resource["license"],
    )


def local_fixture_actor() -> ActorRef:
    return ActorRef(kind="user", id="local-session-user")


def _created_id(result: CommandResult, aggregate_type: str) -> UUID:
    matches = [
        key.split(":", maxsplit=1)[1]
        for key in result.affected_revisions
        if key.startswith(f"{aggregate_type}:")
    ]
    if len(matches) != 1:
        raise RuntimeError(f"CommandResult has no unique {aggregate_type} id")
    return UUID(matches[0])


def load_dev_journey(
    service: JourneyCommandService,
    definition: dict[str, Any],
) -> DevJourneyLoadResult:
    """Execute the stable fixture only through the curated typed service."""

    commands = definition["commands"]
    project = definition["project"]
    inquiry = definition["inquiry"]
    resource = definition["resource"]
    results: list[CommandResult] = []
    ids: dict[str, UUID] = {"workspace": UUID(definition["workspace"]["id"])}

    def execute(payload: dict[str, Any]) -> CommandResult:
        result = service.execute(_REQUEST_ADAPTER.validate_python(payload))
        results.append(result)
        return result

    result = execute({
        "type": "CreateProject", "command_id": commands["project"],
        "expected_revision": 1, "workspace_id": str(ids["workspace"]),
        "title": project["title"], "data_class": project["data_class"],
    })
    ids["project"] = _created_id(result, "project")
    result = execute({
        "type": "CreateInquiry", "command_id": commands["inquiry"],
        "expected_revision": 1, "project_id": str(ids["project"]),
        "question": inquiry["question"], "acceptance": inquiry["acceptance"],
    })
    ids["inquiry"] = _created_id(result, "inquiry")
    result = execute({
        "type": "RegisterResource", "command_id": commands["resource"],
        "expected_revision": 1, "project_id": str(ids["project"]),
        "kind": "local_file", "logical_ref": resource["logical_ref"],
        "media_type": resource["media_type"], "data_class": resource["data_class"],
        "license": resource["license"],
    })
    ids["resource"] = _created_id(result, "resource")
    result = execute({
        "type": "CreateLocator", "command_id": commands["locator"],
        "expected_revision": 1, "resource_id": str(ids["resource"]),
        "locator_type": "local_file",
        "coordinates": {
            "kind": "local_file", "artifact_hash": resource["content_hash"],
            "logical_path": resource["logical_ref"],
            "line_span": {"start_line": resource["start_line"], "end_line": resource["end_line"]},
        },
        "quote_hash": resource["quote_hash"],
    })
    ids["locator"] = _created_id(result, "locator")
    result = execute({
        "type": "CreateClaim", "command_id": commands["claim"],
        "expected_revision": 1, "inquiry_id": str(ids["inquiry"]),
        "statement": definition["claim"]["statement"],
    })
    ids["claim"] = _created_id(result, "claim")
    result = execute({
        "type": "AttachEvidence", "command_id": commands["evidence"],
        "expected_revision": 1, "inquiry_id": str(ids["inquiry"]),
        "locator_id": str(ids["locator"]),
        "direction": definition["evidence"]["direction"],
        "excerpt_hash": resource["quote_hash"],
    })
    ids["evidence"] = _created_id(result, "evidence")
    result = execute({
        "type": "CreateRelation", "command_id": commands["claim_relation"],
        "expected_revision": 1, "relation_type": "evidence_supports_claim",
        "source_type": "evidence", "source_id": str(ids["evidence"]),
        "target_type": "claim", "target_id": str(ids["claim"]),
    })
    ids["claim_relation"] = _created_id(result, "relation")
    result = execute({
        "type": "CreateHypothesis", "command_id": commands["hypothesis"],
        "expected_revision": 1, "inquiry_id": str(ids["inquiry"]),
        **definition["hypothesis"],
    })
    ids["hypothesis"] = _created_id(result, "hypothesis")
    result = execute({
        "type": "ProposePlan", "command_id": commands["plan"],
        "expected_revision": 1, "inquiry_id": str(ids["inquiry"]),
        **definition["plan"],
    })
    ids["plan"] = _created_id(result, "plan")
    result = execute({
        "type": "DraftFinding", "command_id": commands["finding"],
        "expected_revision": 1, "inquiry_id": str(ids["inquiry"]),
        **definition["finding"], "evidence_ids": [str(ids["evidence"])],
        "terminal_run_ids": [],
    })
    ids["finding"] = _created_id(result, "finding")
    return DevJourneyLoadResult(ids=ids, command_results=tuple(results))
