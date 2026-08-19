"""Closed typed command envelopes for the v0.3.0-dev control plane."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from nana_sidecar.contracts.common import (
    ActorRef,
    BudgetSnapshot,
    CapabilityRef,
    ContractModel,
    DataClass,
    EffectScope,
    HashDigest,
    Identifier,
    JsonObject,
    Revision,
    RiskTier,
    normalize_utc_datetime,
    VersionedRef,
)
from nana_sidecar.contracts.domain import (
    CapabilityConstraints,
    Direction,
    PlanStep,
    RelationType,
)
from nana_sidecar.contracts.locators import LocatorCoordinates


class CommandBase(ContractModel):
    command_id: Identifier
    expected_revision: Revision | None = None
    actor: ActorRef


class CreateProject(CommandBase):
    type: Literal["CreateProject"]
    workspace_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=240)]
    data_class: DataClass


class CreateInquiry(CommandBase):
    type: Literal["CreateInquiry"]
    project_id: Identifier
    question: Annotated[str, Field(min_length=1, max_length=4000)]
    acceptance: Annotated[str, Field(min_length=1, max_length=8000)]


class ProposePlan(CommandBase):
    type: Literal["ProposePlan"]
    inquiry_id: Identifier
    steps: tuple[PlanStep, ...] = Field(min_length=1)
    policy: JsonObject
    budget: BudgetSnapshot


class RevisePlan(CommandBase):
    type: Literal["RevisePlan"]
    plan_id: Identifier
    steps: tuple[PlanStep, ...] = Field(min_length=1)
    policy: JsonObject
    budget: BudgetSnapshot


class StartRun(CommandBase):
    type: Literal["StartRun"]
    project_id: Identifier
    inquiry_id: Identifier
    plan_id: Identifier
    plan_revision: Revision
    backend: VersionedRef
    random_seed: int
    retry_of_run_id: Identifier | None = None


class PauseRun(CommandBase):
    type: Literal["PauseRun"]
    run_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class ResumeRun(CommandBase):
    type: Literal["ResumeRun"]
    run_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class CancelRun(CommandBase):
    type: Literal["CancelRun"]
    run_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class ProposeAction(CommandBase):
    type: Literal["ProposeAction"]
    run_id: Identifier | None = None
    plan_step_id: str | None = Field(default=None, min_length=1, max_length=128)
    capability: CapabilityRef
    args_artifact_id: Identifier
    args_hash: HashDigest
    requested_effects: EffectScope
    risk_tier: RiskTier


class CreatePolicyGrant(CommandBase):
    type: Literal["CreatePolicyGrant"]
    project_id: Identifier
    capability: CapabilityRef
    constraints: CapabilityConstraints


class RevokePolicyGrant(CommandBase):
    type: Literal["RevokePolicyGrant"]
    policy_grant_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class RequestApproval(CommandBase):
    type: Literal["RequestApproval"]
    subject_type: Annotated[str, Field(pattern=r"^(action|policy_grant)$")]
    subject_id: Identifier
    subject_hash: HashDigest
    capability: CapabilityRef
    parameter_summary: JsonObject
    requested_effects: EffectScope
    data_class: DataClass
    provider: str | None = Field(default=None, max_length=240)
    budget: BudgetSnapshot
    risk_tier: RiskTier
    reversible: bool
    allowed_uses: Literal[1] = 1
    expires_at: datetime

    _expires_at_utc = field_validator("expires_at")(normalize_utc_datetime)


class DecideApproval(CommandBase):
    type: Literal["DecideApproval"]
    approval_id: Identifier
    subject_hash: HashDigest
    decision: Literal["approved", "denied"]


class AuthorizeAction(CommandBase):
    type: Literal["AuthorizeAction"]
    action_id: Identifier
    action_hash: HashDigest
    authorization_ref: Annotated[str, Field(min_length=1, max_length=240)]


class CommitArtifact(CommandBase):
    type: Literal["CommitArtifact"]
    artifact_id: Identifier
    producer_run_id: Identifier | None = None
    staged_ref: Annotated[str, Field(min_length=1, max_length=2000)]
    blob_hash: HashDigest
    size: int = Field(ge=0)
    media_type: Annotated[str, Field(min_length=1, max_length=160)]
    license: str | None = Field(default=None, max_length=240)
    retention: JsonObject


class RegisterResource(CommandBase):
    type: Literal["RegisterResource"]
    project_id: Identifier
    kind: Annotated[str, Field(min_length=1, max_length=80)]
    logical_ref: Annotated[str, Field(min_length=1, max_length=2000)]
    media_type: Annotated[str, Field(min_length=1, max_length=160)]
    data_class: DataClass
    license: str | None = Field(default=None, max_length=240)


class CreateLocator(CommandBase):
    type: Literal["CreateLocator"]
    resource_id: Identifier
    locator_type: Annotated[
        str,
        Field(pattern=r"^(web|pdf|repo|local_file|dataset|run_output)$"),
    ]
    coordinates: LocatorCoordinates
    quote_hash: HashDigest | None = None

    @model_validator(mode="after")
    def type_matches_coordinates(self) -> "CreateLocator":
        if self.locator_type != self.coordinates.kind:
            raise ValueError("locator_type must match coordinates.kind")
        return self


class CreateClaim(CommandBase):
    type: Literal["CreateClaim"]
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]


class AttachEvidence(CommandBase):
    type: Literal["AttachEvidence"]
    inquiry_id: Identifier
    locator_id: Identifier
    direction: Direction
    excerpt_hash: HashDigest | None = None


class CreateHypothesis(CommandBase):
    type: Literal["CreateHypothesis"]
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    falsification_criteria: Annotated[str, Field(min_length=1, max_length=8000)]


class DraftFinding(CommandBase):
    type: Literal["DraftFinding"]
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    confidence_basis: Annotated[str, Field(min_length=1, max_length=8000)]
    evidence_ids: tuple[Identifier, ...] = ()
    terminal_run_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def require_provenance(self) -> "DraftFinding":
        if not self.evidence_ids and not self.terminal_run_ids:
            raise ValueError(
                "Finding draft must reference Evidence or a terminal Run."
            )
        return self


class CreateRelation(CommandBase):
    type: Literal["CreateRelation"]
    relation_type: RelationType
    source_type: Annotated[str, Field(min_length=1, max_length=80)]
    source_id: Identifier
    target_type: Annotated[str, Field(min_length=1, max_length=80)]
    target_id: Identifier


class PublishExport(CommandBase):
    type: Literal["PublishExport"]
    project_id: Identifier
    artifact_id: Identifier
    destination_token: Annotated[str, Field(min_length=1, max_length=500)]
    expected_media_type: Annotated[str, Field(min_length=1, max_length=160)]
    action_id: Identifier
    action_hash: HashDigest


Command = Annotated[
    Union[
        CreateProject,
        CreateInquiry,
        ProposePlan,
        RevisePlan,
        StartRun,
        PauseRun,
        ResumeRun,
        CancelRun,
        ProposeAction,
        CreatePolicyGrant,
        RevokePolicyGrant,
        RequestApproval,
        DecideApproval,
        AuthorizeAction,
        CommitArtifact,
        RegisterResource,
        CreateLocator,
        CreateClaim,
        AttachEvidence,
        CreateHypothesis,
        DraftFinding,
        CreateRelation,
        PublishExport,
    ],
    Field(discriminator="type"),
]


DEV_COMMAND_NAMES = frozenset(
    command.__name__
    for command in (
        CreateProject,
        CreateInquiry,
        ProposePlan,
        RevisePlan,
        StartRun,
        PauseRun,
        ResumeRun,
        CancelRun,
        ProposeAction,
        CreatePolicyGrant,
        RevokePolicyGrant,
        RequestApproval,
        DecideApproval,
        AuthorizeAction,
        CommitArtifact,
        RegisterResource,
        CreateLocator,
        CreateClaim,
        AttachEvidence,
        CreateHypothesis,
        DraftFinding,
        CreateRelation,
        PublishExport,
    )
)


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REPLAYED = "replayed"


class CommandResult(ContractModel):
    command_id: Identifier
    status: CommandStatus
    affected_revisions: dict[str, Revision]
    event_ids: tuple[int, ...]
