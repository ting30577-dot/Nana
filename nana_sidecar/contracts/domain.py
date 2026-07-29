"""Stable control-plane and research-semantic DTOs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from nana_sidecar.contracts.common import (
    ActorRef,
    BudgetSnapshot,
    ContractModel,
    DataClass,
    EffectScope,
    HashDigest,
    Identifier,
    JsonObject,
    ResourceUsage,
    Revision,
    RiskTier,
    VersionedRef,
)
from nana_sidecar.contracts.locators import (
    LocatorCoordinates,
    validate_logical_path,
)


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    SAFE_MODE = "safe_mode"
    READ_ONLY = "read_only"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class InquiryStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ACTIVE = "active"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    DECIDED = "decided"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RunState(StrEnum):
    PROPOSED = "proposed"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BUDGET_EXCEEDED = "budget_exceeded"
    ORPHANED = "orphaned"


class ActionState(StrEnum):
    PROPOSED = "proposed"
    WAITING_APPROVAL = "waiting_approval"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    DENIED = "denied"
    EXPIRED = "expired"
    EFFECT_UNKNOWN = "effect_unknown"


class PolicyDecision(StrEnum):
    AUTO = "auto"
    GRANT = "grant"
    APPROVAL_REQUIRED = "approval_required"
    DENIED = "denied"


class ArtifactState(StrEnum):
    STAGED = "staged"
    AVAILABLE = "available"
    FAILED = "failed"
    ORPHAN_QUARANTINED = "orphan_quarantined"
    CORRUPT = "corrupt"
    TOMBSTONED = "tombstoned"
    GARBAGE_COLLECTED = "garbage_collected"


class Direction(StrEnum):
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    LIMITS = "limits"


class ResourceStatus(StrEnum):
    DRAFT = "draft"
    AVAILABLE = "available"
    STALE = "stale"
    FAILED = "failed"
    TOMBSTONED = "tombstoned"


class LocatorStatus(StrEnum):
    DRAFT = "draft"
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"
    SOURCE_UNAVAILABLE = "source_unavailable"
    TOMBSTONED = "tombstoned"


class ClaimStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    VERIFIED = "verified"
    CONTESTED = "contested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidenceStatus(StrEnum):
    LEAD = "lead"
    VALID = "valid"
    REJECTED = "rejected"
    STALE = "stale"
    SOURCE_UNAVAILABLE = "source_unavailable"
    TOMBSTONED = "tombstoned"


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    TESTING = "testing"
    SUPPORTED = "supported"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"
    SUPERSEDED = "superseded"


class MethodStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class FindingStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class DecisionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RelationStatus(StrEnum):
    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


class RelationType(StrEnum):
    RESOURCE_CONTAINS_EVIDENCE = "resource_contains_evidence"
    EVIDENCE_SUPPORTS_CLAIM = "evidence_supports_claim"
    EVIDENCE_OPPOSES_CLAIM = "evidence_opposes_claim"
    EVIDENCE_LIMITS_CLAIM = "evidence_limits_claim"
    HYPOTHESIS_TESTED_BY_RUN = "hypothesis_tested_by_run"
    RUN_PRODUCES_ARTIFACT = "run_produces_artifact"
    RUN_PRODUCES_FINDING = "run_produces_finding"
    FINDING_INFORMS_DECISION = "finding_informs_decision"
    DECISION_ACCEPTS_METHOD = "decision_accepts_method"
    ARTIFACT_DERIVED_FROM_ARTIFACT = "artifact_derived_from_artifact"
    RUN_RETRY_OF_RUN = "run_retry_of_run"
    OBJECT_SUPERSEDES_OBJECT = "object_supersedes_object"


class PolicyGrantState(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"


class ApprovalDecision(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class AuthorizationSource(StrEnum):
    AUTO_POLICY = "auto_policy"
    POLICY_GRANT = "policy_grant"
    APPROVAL = "approval"


class ReceiptResult(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    EFFECT_UNKNOWN = "effect_unknown"


class EventType(StrEnum):
    WORKSPACE_CREATED = "workspace.created"
    PROJECT_CREATED = "project.created"
    PROJECT_STATUS_CHANGED = "project.status_changed"
    INQUIRY_CREATED = "inquiry.created"
    INQUIRY_STATUS_CHANGED = "inquiry.status_changed"
    PLAN_PROPOSED = "plan.proposed"
    PLAN_REVISED = "plan.revised"
    PLAN_STATUS_CHANGED = "plan.status_changed"
    RUN_CREATED = "run.created"
    RUN_STARTED = "run.started"
    RUN_HEARTBEAT = "run.heartbeat"
    RUN_PAUSED = "run.paused"
    RUN_CANCELLED = "run.cancelled"
    RUN_TIMED_OUT = "run.timed_out"
    RUN_FAILED = "run.failed"
    RUN_SUCCEEDED = "run.succeeded"
    RUN_BUDGET_EXCEEDED = "run.budget_exceeded"
    RUN_ORPHANED = "run.orphaned"
    PLAN_STEP_STARTED = "plan.step.started"
    PLAN_STEP_COMPLETED = "plan.step.completed"
    PLAN_STEP_FAILED = "plan.step.failed"
    ACTION_PROPOSED = "action.proposed"
    ACTION_AUTHORIZED = "action.authorized"
    ACTION_STARTED = "action.started"
    ACTION_OUTPUT = "action.output"
    ACTION_COMPLETED = "action.completed"
    ACTION_EFFECT_UNKNOWN = "action.effect_unknown"
    ARTIFACT_STAGED = "artifact.staged"
    ARTIFACT_COMMITTED = "artifact.committed"
    ARTIFACT_RECONCILED = "artifact.reconciled"
    BUDGET_UPDATED = "budget.updated"
    BUDGET_THRESHOLD_REACHED = "budget.threshold_reached"
    POLICY_GRANT_CREATED = "policy_grant.created"
    POLICY_GRANT_REVOKED = "policy_grant.revoked"
    POLICY_GRANT_EXPIRED = "policy_grant.expired"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    APPROVAL_EXPIRED = "approval.expired"
    RESOURCE_REGISTERED = "resource.registered"
    LOCATOR_CREATED = "locator.created"
    CLAIM_CREATED = "claim.created"
    EVIDENCE_ATTACHED = "evidence.attached"
    HYPOTHESIS_CREATED = "hypothesis.created"
    FINDING_DRAFTED = "finding.drafted"
    RELATION_CREATED = "relation.created"
    EXPORT_PUBLISHED = "export.published"


class Workspace(ContractModel):
    id: Identifier
    schema_version: int = Field(ge=1)
    data_root: Annotated[str, Field(min_length=1, max_length=2000)]
    policy: JsonObject
    status: WorkspaceStatus
    revision: Revision
    created_at: datetime


class Project(ContractModel):
    id: Identifier
    workspace_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=240)]
    status: ProjectStatus = ProjectStatus.ACTIVE
    data_class: DataClass
    revision: Revision
    created_at: datetime


class Inquiry(ContractModel):
    id: Identifier
    project_id: Identifier
    question: Annotated[str, Field(min_length=1, max_length=4000)]
    acceptance: Annotated[str, Field(min_length=1, max_length=8000)]
    status: InquiryStatus = InquiryStatus.DRAFT
    revision: Revision
    created_at: datetime


class PlanStep(ContractModel):
    id: Annotated[str, Field(min_length=1, max_length=128)]
    title: Annotated[str, Field(min_length=1, max_length=240)]
    capability_id: str | None = Field(default=None, min_length=1, max_length=160)
    expected_artifacts: tuple[str, ...] = ()
    approval_required: bool = False


class Plan(ContractModel):
    id: Identifier
    inquiry_id: Identifier
    revision: Revision
    status: PlanStatus
    steps: tuple[PlanStep, ...] = Field(min_length=1)
    policy: JsonObject
    budget: BudgetSnapshot
    created_at: datetime


class CodeSnapshot(ContractModel):
    commit_ref: str | None = Field(default=None, min_length=1, max_length=160)
    diff_hash: HashDigest | None = None
    dirty: bool


class EnvironmentSnapshot(ContractModel):
    os_name: Annotated[str, Field(min_length=1, max_length=160)]
    os_version: Annotated[str, Field(min_length=1, max_length=160)]
    python_version: Annotated[str, Field(min_length=1, max_length=80)]
    dependency_lock_hash: HashDigest
    environment_keys: tuple[str, ...] = ()


class RunSnapshot(ContractModel):
    plan_id: Identifier
    plan_revision: Revision
    capabilities: tuple[VersionedRef, ...]
    models: tuple[VersionedRef, ...] = ()
    backend: VersionedRef
    policy: JsonObject
    budget: BudgetSnapshot
    code: CodeSnapshot
    input_artifact_ids: tuple[Identifier, ...] = ()
    environment: EnvironmentSnapshot
    random_seed: int


class Run(ContractModel):
    id: Identifier
    project_id: Identifier
    inquiry_id: Identifier
    state: RunState
    snapshot: RunSnapshot
    retry_of_run_id: Identifier | None = None
    result: JsonObject | None = None
    created_at: datetime
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def terminal_timestamp(self) -> "Run":
        terminal = {
            RunState.SUCCEEDED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
            RunState.BUDGET_EXCEEDED,
            RunState.ORPHANED,
        }
        if self.state in terminal and self.finished_at is None:
            raise ValueError("terminal Run requires finished_at")
        if self.state not in terminal and self.finished_at is not None:
            raise ValueError("non-terminal Run cannot have finished_at")
        return self


class Action(ContractModel):
    id: Identifier
    run_id: Identifier | None = None
    plan_step_id: str | None = Field(default=None, min_length=1, max_length=128)
    capability: VersionedRef
    args_artifact_id: Identifier
    args_hash: HashDigest
    action_hash: HashDigest
    risk_tier: RiskTier
    requested_effects: EffectScope
    policy_decision: PolicyDecision
    authorization_ref: str | None = Field(default=None, max_length=240)
    state: ActionState
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ArtifactStagedPayload(ContractModel):
    artifact_id: Identifier
    state: Literal[ArtifactState.STAGED] = ArtifactState.STAGED
    temp_ref: Annotated[str, Field(min_length=1, max_length=2000)]
    blob_hash: HashDigest
    size: int = Field(ge=0)
    media_type: Annotated[str, Field(min_length=1, max_length=160)]

    _relative_temp_ref = field_validator("temp_ref")(validate_logical_path)


class ArtifactCommittedPayload(ContractModel):
    artifact_id: Identifier
    state: Literal[ArtifactState.AVAILABLE] = ArtifactState.AVAILABLE
    blob_hash: HashDigest
    size: int = Field(ge=0)
    media_type: Annotated[str, Field(min_length=1, max_length=160)]


class ArtifactReconciledPayload(ContractModel):
    artifact_id: Identifier
    previous_state: ArtifactState
    state: ArtifactState
    reason_code: Annotated[str, Field(min_length=1, max_length=160)]

    @model_validator(mode="after")
    def valid_reconciliation_transition(self) -> "ArtifactReconciledPayload":
        allowed = {
            ArtifactState.STAGED: {
                ArtifactState.AVAILABLE,
                ArtifactState.FAILED,
                ArtifactState.ORPHAN_QUARANTINED,
            },
            ArtifactState.AVAILABLE: {
                ArtifactState.CORRUPT,
            },
            ArtifactState.FAILED: {
                ArtifactState.AVAILABLE,
                ArtifactState.GARBAGE_COLLECTED,
            },
            ArtifactState.ORPHAN_QUARANTINED: {
                ArtifactState.AVAILABLE,
                ArtifactState.GARBAGE_COLLECTED,
            },
            ArtifactState.CORRUPT: {
                ArtifactState.AVAILABLE,
                ArtifactState.TOMBSTONED,
            },
        }
        if self.state not in allowed.get(self.previous_state, set()):
            raise ValueError("invalid Artifact reconciliation transition")
        return self


ARTIFACT_EVENT_PAYLOADS = {
    EventType.ARTIFACT_STAGED: ArtifactStagedPayload,
    EventType.ARTIFACT_COMMITTED: ArtifactCommittedPayload,
    EventType.ARTIFACT_RECONCILED: ArtifactReconciledPayload,
}


class Event(ContractModel):
    id: int = Field(ge=1)
    aggregate_type: Annotated[str, Field(min_length=1, max_length=80)]
    aggregate_id: Identifier
    aggregate_version: Revision
    run_id: Identifier | None = None
    run_seq: int | None = Field(default=None, ge=1)
    action_id: Identifier | None = None
    actor: ActorRef
    causation_id: str | None = Field(default=None, max_length=160)
    correlation_id: str | None = Field(default=None, max_length=160)
    type: EventType
    payload: JsonObject | None = None
    payload_artifact_id: Identifier | None = None
    occurred_at: datetime

    @model_validator(mode="after")
    def exactly_one_payload(self) -> "Event":
        if (self.payload is None) == (self.payload_artifact_id is None):
            raise ValueError(
                "Event requires exactly one of payload or payload_artifact_id"
            )
        if self.run_id is None and self.run_seq is not None:
            raise ValueError("run_seq requires run_id")
        payload_model = ARTIFACT_EVENT_PAYLOADS.get(self.type)
        if payload_model is not None:
            if self.aggregate_type != "artifact":
                raise ValueError(
                    "Artifact lifecycle Event requires artifact aggregate"
                )
            if self.payload is None:
                raise ValueError(
                    "Artifact lifecycle Event requires inline typed payload"
                )
            typed_payload = payload_model.model_validate(self.payload)
            if typed_payload.artifact_id != self.aggregate_id:
                raise ValueError(
                    "Artifact Event payload id must match aggregate_id"
                )
        return self


class ArtifactStagedEvent(Event):
    type: Literal[EventType.ARTIFACT_STAGED]
    payload: ArtifactStagedPayload
    payload_artifact_id: Literal[None] = None


class ArtifactCommittedEvent(Event):
    type: Literal[EventType.ARTIFACT_COMMITTED]
    payload: ArtifactCommittedPayload
    payload_artifact_id: Literal[None] = None


class ArtifactReconciledEvent(Event):
    type: Literal[EventType.ARTIFACT_RECONCILED]
    payload: ArtifactReconciledPayload
    payload_artifact_id: Literal[None] = None


ArtifactLifecycleEvent = Annotated[
    Union[
        ArtifactStagedEvent,
        ArtifactCommittedEvent,
        ArtifactReconciledEvent,
    ],
    Field(discriminator="type"),
]


class CapabilityConstraints(ContractModel):
    args_schema: JsonObject
    allowed_data_classes: tuple[DataClass, ...] = Field(min_length=1)
    allowed_providers: tuple[str, ...] = ()
    read_roots: tuple[str, ...] = ()
    write_roots: tuple[str, ...] = ()
    network_targets: tuple[str, ...] = ()
    network_methods: tuple[str, ...] = ()
    per_action_budget: BudgetSnapshot
    cumulative_budget: BudgetSnapshot
    max_concurrency: int = Field(gt=0)
    max_uses: int = Field(gt=0)
    valid_from: datetime
    expires_at: datetime
    revoke_conditions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_window(self) -> "CapabilityConstraints":
        if self.expires_at <= self.valid_from:
            raise ValueError("PolicyGrant expiry must be after valid_from")
        return self


class PolicyGrant(ContractModel):
    id: Identifier
    project_id: Identifier
    capability: VersionedRef
    constraints: CapabilityConstraints
    state: PolicyGrantState
    uses: int = Field(ge=0)
    created_at: datetime

    @model_validator(mode="after")
    def uses_within_limit(self) -> "PolicyGrant":
        if self.uses > self.constraints.max_uses:
            raise ValueError("PolicyGrant uses exceed max_uses")
        return self


class Approval(ContractModel):
    id: Identifier
    subject_type: Annotated[str, Field(pattern=r"^(action|policy_grant)$")]
    subject_id: Identifier
    subject_hash: HashDigest
    capability: VersionedRef
    parameter_summary: JsonObject
    requested_effects: EffectScope
    data_class: DataClass
    provider: str | None = Field(default=None, max_length=240)
    budget: BudgetSnapshot
    risk_tier: RiskTier
    reversible: bool
    allowed_uses: int = Field(ge=1)
    expires_at: datetime
    decision: ApprovalDecision
    decided_by: ActorRef | None = None
    decided_at: datetime | None = None

    @model_validator(mode="after")
    def decision_audit(self) -> "Approval":
        decided = self.decision is not ApprovalDecision.REQUESTED
        if decided != (self.decided_at is not None):
            raise ValueError("decided Approval must have decided_at")
        if decided != (self.decided_by is not None):
            raise ValueError("decided Approval must have decided_by")
        return self


class ActionReceipt(ContractModel):
    id: Identifier
    action_id: Identifier
    action_hash: HashDigest
    authorization_source: AuthorizationSource
    authorization_ref: Annotated[str, Field(min_length=1, max_length=240)]
    approved_by: ActorRef | None = None
    approved_at: datetime | None = None
    actual_effects: EffectScope
    result: ReceiptResult
    exit_code: int | None = None
    before_artifact_ids: tuple[Identifier, ...] = ()
    after_artifact_ids: tuple[Identifier, ...] = ()
    diff_artifact_id: Identifier | None = None
    resource_usage: ResourceUsage
    undo_ref: str | None = Field(default=None, max_length=2000)
    compensating_action_id: Identifier | None = None
    created_at: datetime

    @model_validator(mode="after")
    def approval_provenance(self) -> "ActionReceipt":
        approved = self.authorization_source is AuthorizationSource.APPROVAL
        if approved and (self.approved_by is None or self.approved_at is None):
            raise ValueError("approval-authorized Receipt requires approver and time")
        if not approved and (self.approved_by is not None or self.approved_at is not None):
            raise ValueError("non-approval Receipt cannot claim an approver")
        return self


class Artifact(ContractModel):
    id: Identifier
    media_type: Annotated[str, Field(min_length=1, max_length=160)]
    blob_hash: HashDigest
    size: int = Field(ge=0)
    state: ArtifactState
    producer_run_id: Identifier | None = None
    license: str | None = Field(default=None, max_length=240)
    retention: JsonObject
    created_at: datetime


class Resource(ContractModel):
    id: Identifier
    project_id: Identifier
    kind: Annotated[str, Field(min_length=1, max_length=80)]
    logical_ref: Annotated[str, Field(min_length=1, max_length=2000)]
    content_hash: HashDigest | None = None
    media_type: Annotated[str, Field(min_length=1, max_length=160)]
    data_class: DataClass
    license: str | None = Field(default=None, max_length=240)
    captured_at: datetime
    status: ResourceStatus
    revision: Revision


class Locator(ContractModel):
    id: Identifier
    resource_id: Identifier
    locator_type: Annotated[
        str,
        Field(pattern=r"^(web|pdf|repo|local_file|dataset|run_output)$"),
    ]
    coordinates: LocatorCoordinates
    quote_hash: HashDigest | None = None
    parser_id: str | None = Field(default=None, max_length=160)
    parser_version: str | None = Field(default=None, max_length=80)
    status: LocatorStatus
    revision: Revision

    @model_validator(mode="after")
    def type_matches_coordinates(self) -> "Locator":
        if self.locator_type != self.coordinates.kind:
            raise ValueError("locator_type must match coordinates.kind")
        return self


class Claim(ContractModel):
    id: Identifier
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    status: ClaimStatus
    revision: Revision
    created_by: ActorRef


class Evidence(ContractModel):
    id: Identifier
    inquiry_id: Identifier
    locator_id: Identifier
    direction: Direction
    excerpt_hash: HashDigest | None = None
    status: EvidenceStatus
    created_by: ActorRef


class Hypothesis(ContractModel):
    id: Identifier
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    falsification_criteria: Annotated[str, Field(min_length=1, max_length=8000)]
    status: HypothesisStatus
    created_by: ActorRef


class Method(ContractModel):
    id: Identifier
    project_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=500)]
    preconditions: Annotated[str, Field(min_length=1, max_length=8000)]
    procedure_artifact_id: Identifier
    status: MethodStatus
    revision: Revision
    created_by: ActorRef


class Finding(ContractModel):
    id: Identifier
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    status: FindingStatus
    confidence_basis: Annotated[str, Field(min_length=1, max_length=8000)]
    evidence_ids: tuple[Identifier, ...] = ()
    producer_run_id: Identifier | None = None
    revision: Revision

    @model_validator(mode="after")
    def require_provenance(self) -> "Finding":
        if not self.evidence_ids and self.producer_run_id is None:
            raise ValueError("Finding requires Evidence or a terminal Run")
        return self


class Decision(ContractModel):
    id: Identifier
    inquiry_id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8000)]
    alternatives: tuple[str, ...]
    limitations: tuple[str, ...]
    reevaluate_when: Annotated[str, Field(min_length=1, max_length=8000)]
    status: DecisionStatus
    revision: Revision
    confirmed_by: ActorRef | None = None
    confirmed_at: datetime | None = None

    @model_validator(mode="after")
    def confirmation_provenance(self) -> "Decision":
        confirmed = self.status is DecisionStatus.CONFIRMED
        if confirmed != (self.confirmed_by is not None):
            raise ValueError("confirmed Decision requires confirmed_by")
        if confirmed != (self.confirmed_at is not None):
            raise ValueError("confirmed Decision requires confirmed_at")
        return self


class Relation(ContractModel):
    id: Identifier
    type: RelationType
    source_type: Annotated[str, Field(min_length=1, max_length=80)]
    source_id: Identifier
    target_type: Annotated[str, Field(min_length=1, max_length=80)]
    target_id: Identifier
    producer_run_id: Identifier | None = None
    created_by: ActorRef
    status: RelationStatus
