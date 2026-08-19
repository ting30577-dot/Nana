"""Closed D3-05 browser requests and internal Workspace bootstrap input."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from nana_sidecar.contracts.commands import (
    AttachEvidence,
    Command,
    CreateClaim,
    CreateHypothesis,
    CreateInquiry,
    CreateLocator,
    CreateProject,
    CreateRelation,
    DraftFinding,
    DecideApproval,
    ProposePlan,
    RegisterResource,
    RevisePlan,
    StartRun,
    PauseRun,
    ResumeRun,
    CancelRun,
)
from nana_sidecar.contracts.common import (
    ActorRef,
    BudgetSnapshot,
    ContractModel,
    DataClass,
    HashDigest,
    Identifier,
    JsonObject,
    Revision,
    normalize_utc_datetime,
)
from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_CAPABILITY,
)
from nana_sidecar.contracts.domain import Direction, PlanStep, RelationType
from nana_sidecar.contracts.locators import (
    LocalFileCoordinates,
    validate_logical_path,
)


class JourneyRequestBase(ContractModel):
    """Browser-safe Command prefix; actor is deliberately absent."""

    command_id: Identifier
    expected_revision: Revision


class CreateProjectRequest(JourneyRequestBase):
    type: Literal["CreateProject"]
    workspace_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=240)]
    data_class: DataClass


class CreateInquiryRequest(JourneyRequestBase):
    type: Literal["CreateInquiry"]
    project_id: Identifier
    question: Annotated[str, Field(min_length=1, max_length=4000)]
    acceptance: Annotated[str, Field(min_length=1, max_length=8000)]


class _PlanRequest(JourneyRequestBase):
    steps: tuple[PlanStep, ...] = Field(min_length=1, max_length=64)
    policy: JsonObject
    budget: BudgetSnapshot

    @model_validator(mode="after")
    def unique_step_ids(self) -> "_PlanRequest":
        identifiers = tuple(step.id for step in self.steps)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Plan step ids must be unique")
        return self


class ProposePlanRequest(_PlanRequest):
    type: Literal["ProposePlan"]
    inquiry_id: Identifier


class RevisePlanRequest(_PlanRequest):
    type: Literal["RevisePlan"]
    plan_id: Identifier


class StartRunRequest(JourneyRequestBase):
    """Browser-safe locked T2 start; fixture inputs stay server-owned."""

    type: Literal["StartRun"]
    project_id: Identifier
    inquiry_id: Identifier
    plan_id: Identifier
    plan_revision: Revision
    random_seed: int
    retry_of_run_id: Identifier | None = None


class PauseRunRequest(JourneyRequestBase):
    type: Literal["PauseRun"]
    run_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class ResumeRunRequest(JourneyRequestBase):
    type: Literal["ResumeRun"]
    run_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class CancelRunRequest(JourneyRequestBase):
    type: Literal["CancelRun"]
    run_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


class RegisterResourceRequest(JourneyRequestBase):
    type: Literal["RegisterResource"]
    project_id: Identifier
    kind: Literal["local_file"]
    logical_ref: Annotated[str, Field(min_length=1, max_length=2000)]
    media_type: Annotated[str, Field(min_length=1, max_length=160)]
    data_class: DataClass
    license: str | None = Field(default=None, max_length=240)

    _portable_ref = field_validator("logical_ref")(validate_logical_path)


class CreateLocatorRequest(JourneyRequestBase):
    type: Literal["CreateLocator"]
    resource_id: Identifier
    locator_type: Literal["local_file"]
    coordinates: LocalFileCoordinates
    quote_hash: HashDigest


class CreateClaimRequest(JourneyRequestBase):
    type: Literal["CreateClaim"]
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]


class AttachEvidenceRequest(JourneyRequestBase):
    type: Literal["AttachEvidence"]
    inquiry_id: Identifier
    locator_id: Identifier
    direction: Direction
    excerpt_hash: HashDigest


class CreateHypothesisRequest(JourneyRequestBase):
    type: Literal["CreateHypothesis"]
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    falsification_criteria: Annotated[str, Field(min_length=1, max_length=8000)]


class CreateRelationRequest(JourneyRequestBase):
    type: Literal["CreateRelation"]
    relation_type: Literal[
        RelationType.EVIDENCE_SUPPORTS_CLAIM,
        RelationType.EVIDENCE_OPPOSES_CLAIM,
        RelationType.EVIDENCE_LIMITS_CLAIM,
    ]
    source_type: Literal["evidence"]
    source_id: Identifier
    target_type: Literal["claim"]
    target_id: Identifier


class DraftFindingRequest(JourneyRequestBase):
    type: Literal["DraftFinding"]
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    confidence_basis: Annotated[str, Field(min_length=1, max_length=8000)]
    evidence_ids: tuple[Identifier, ...] = Field(default=(), max_length=128)
    terminal_run_ids: tuple[Identifier, ...] = Field(default=(), max_length=1)

    @model_validator(mode="after")
    def valid_provenance(self) -> "DraftFindingRequest":
        if not self.evidence_ids and not self.terminal_run_ids:
            raise ValueError(
                "Finding draft must reference Evidence or a terminal Run."
            )
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Finding Evidence ids must be unique")
        return self


class RequestApprovalRequest(JourneyRequestBase):
    """Prepare one exact server-derived draft-export subject."""

    type: Literal["RequestApproval"]
    finding_id: Identifier
    target_selection_id: Annotated[
        str,
        Field(min_length=43, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    ]


class DecideApprovalRequest(JourneyRequestBase):
    """Decide one already-projected Approval without supplying authority."""

    type: Literal["DecideApproval"]
    approval_id: Identifier
    subject_hash: HashDigest
    decision: Literal["approved", "denied"]


JourneyCommandRequest = Annotated[
    Union[
        CreateProjectRequest,
        CreateInquiryRequest,
        ProposePlanRequest,
        RevisePlanRequest,
        StartRunRequest,
        PauseRunRequest,
        ResumeRunRequest,
        CancelRunRequest,
        RegisterResourceRequest,
        CreateLocatorRequest,
        CreateClaimRequest,
        AttachEvidenceRequest,
        CreateHypothesisRequest,
        CreateRelationRequest,
        DraftFindingRequest,
        RequestApprovalRequest,
        DecideApprovalRequest,
    ],
    Field(discriminator="type"),
]


JOURNEY_COMMAND_NAMES = frozenset(
    {
        "CreateProject",
        "CreateInquiry",
        "ProposePlan",
        "RevisePlan",
        "StartRun",
        "PauseRun",
        "ResumeRun",
        "CancelRun",
        "RegisterResource",
        "CreateLocator",
        "CreateClaim",
        "AttachEvidence",
        "CreateHypothesis",
        "CreateRelation",
        "DraftFinding",
        "RequestApproval",
        "DecideApproval",
    }
)


class WorkspaceBootstrapSpec(ContractModel):
    workspace_id: Identifier
    data_root: Annotated[str, Field(min_length=1, max_length=2000)]
    policy: JsonObject = Field(default_factory=dict)
    status: Literal["active"] = "active"
    revision: Literal[1] = 1
    created_at: datetime

    _created_at_utc = field_validator("created_at")(normalize_utc_datetime)
    _portable_data_root = field_validator("data_root")(validate_logical_path)


def to_canonical_command(
    request: JourneyCommandRequest,
    *,
    actor: ActorRef,
) -> Command:
    """Inject the audited local principal into one curated request."""

    values = request.model_dump(mode="python")
    values["actor"] = actor
    if isinstance(request, StartRunRequest):
        values["backend"] = {
            "id": PYTHON_UNITTEST_LOCKED_CAPABILITY.id,
            "version": PYTHON_UNITTEST_LOCKED_CAPABILITY.version,
        }
    if isinstance(request, RequestApprovalRequest):
        raise TypeError(
            "RequestApproval is composed from canonical server facts by the export service"
        )
    command_types = {
        "CreateProject": CreateProject,
        "CreateInquiry": CreateInquiry,
        "ProposePlan": ProposePlan,
        "RevisePlan": RevisePlan,
        "StartRun": StartRun,
        "PauseRun": PauseRun,
        "ResumeRun": ResumeRun,
        "CancelRun": CancelRun,
        "RegisterResource": RegisterResource,
        "CreateLocator": CreateLocator,
        "CreateClaim": CreateClaim,
        "AttachEvidence": AttachEvidence,
        "CreateHypothesis": CreateHypothesis,
        "CreateRelation": CreateRelation,
        "DraftFinding": DraftFinding,
        "DecideApproval": DecideApproval,
    }
    return command_types[request.type].model_validate(values)
