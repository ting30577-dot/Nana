"""A wrapper that makes the complete D0 schema visible in OpenAPI."""

from __future__ import annotations

from nana_sidecar.contracts.authorization import (
    ActionHashMaterial,
    AuthorizationMatch,
    GrantMatchContext,
)
from nana_sidecar.contracts.capabilities import CapabilityRegistryEntry
from nana_sidecar.contracts.commands import Command, CommandResult
from nana_sidecar.contracts.common import ContractModel
from nana_sidecar.contracts.errors import ErrorResponse
from nana_sidecar.contracts.domain import (
    Action,
    ActionReceipt,
    Approval,
    Artifact,
    ArtifactLifecycleEvent,
    Claim,
    Evidence,
    Event,
    Finding,
    Hypothesis,
    Inquiry,
    Locator,
    Method,
    Plan,
    PolicyGrant,
    Project,
    Relation,
    Resource,
    Run,
    Decision,
    Workspace,
)


class ContractCatalogSchema(ContractModel):
    command: Command
    command_result: CommandResult
    error_response: ErrorResponse
    action_hash_material: ActionHashMaterial
    capability_registry_entry: CapabilityRegistryEntry
    grant_match_context: GrantMatchContext
    authorization_match: AuthorizationMatch
    workspace: Workspace
    project: Project
    inquiry: Inquiry
    plan: Plan
    run: Run
    action: Action
    event: Event
    policy_grant: PolicyGrant
    approval: Approval
    action_receipt: ActionReceipt
    artifact: Artifact
    artifact_lifecycle_event: ArtifactLifecycleEvent
    resource: Resource
    locator: Locator
    claim: Claim
    evidence: Evidence
    hypothesis: Hypothesis
    method: Method
    finding: Finding
    decision: Decision
    relation: Relation
