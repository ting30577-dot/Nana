"""Closed Relation Registry and deterministic invariant validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from nana_sidecar.contracts.domain import RelationType


@dataclass(frozen=True, slots=True)
class RelationRule:
    source_type: str
    target_type: str
    outgoing_max: int | None
    incoming_max: int | None
    deletion_behavior: str
    same_inquiry: bool = False
    same_project: bool = True
    required_direction: str | None = None
    acyclic: bool = False
    require_source_newer: bool = False
    error_code: str = "E_REL_INVALID"


RELATION_REGISTRY: dict[str, RelationRule] = {
    RelationType.RESOURCE_CONTAINS_EVIDENCE.value: RelationRule(
        "resource",
        "evidence",
        None,
        1,
        "preserve relation; Evidence becomes source_unavailable",
        error_code="E_REL_RESOURCE_MISMATCH",
    ),
    RelationType.EVIDENCE_SUPPORTS_CLAIM.value: RelationRule(
        "evidence",
        "claim",
        None,
        None,
        "tombstone relation; preserve both endpoints",
        same_inquiry=True,
        required_direction="supports",
        error_code="E_REL_EVIDENCE_DIRECTION",
    ),
    RelationType.EVIDENCE_OPPOSES_CLAIM.value: RelationRule(
        "evidence",
        "claim",
        None,
        None,
        "tombstone relation; preserve both endpoints",
        same_inquiry=True,
        required_direction="opposes",
        error_code="E_REL_EVIDENCE_DIRECTION",
    ),
    RelationType.EVIDENCE_LIMITS_CLAIM.value: RelationRule(
        "evidence",
        "claim",
        None,
        None,
        "tombstone relation; preserve both endpoints",
        same_inquiry=True,
        required_direction="limits",
        error_code="E_REL_EVIDENCE_DIRECTION",
    ),
    RelationType.HYPOTHESIS_TESTED_BY_RUN.value: RelationRule(
        "hypothesis",
        "run",
        None,
        None,
        "preserve both endpoints",
        same_inquiry=True,
        error_code="E_REL_CROSS_PROJECT",
    ),
    RelationType.RUN_PRODUCES_ARTIFACT.value: RelationRule(
        "run",
        "artifact",
        None,
        1,
        "preserve provenance when Artifact is tombstoned",
        error_code="E_REL_PRODUCER_EXISTS",
    ),
    RelationType.RUN_PRODUCES_FINDING.value: RelationRule(
        "run",
        "finding",
        None,
        1,
        "preserve provenance; replacement creates a revision",
        same_inquiry=True,
        error_code="E_REL_FINDING_SCOPE",
    ),
    RelationType.FINDING_INFORMS_DECISION.value: RelationRule(
        "finding",
        "decision",
        None,
        None,
        "preserve both endpoints",
        same_inquiry=True,
        error_code="E_REL_DECISION_EMPTY",
    ),
    RelationType.DECISION_ACCEPTS_METHOD.value: RelationRule(
        "decision",
        "method",
        None,
        None,
        "preserve both endpoints",
        error_code="E_REL_METHOD_SCOPE",
    ),
    RelationType.ARTIFACT_DERIVED_FROM_ARTIFACT.value: RelationRule(
        "artifact",
        "artifact",
        None,
        None,
        "preserve lineage after tombstone",
        same_project=False,
        acyclic=True,
        error_code="E_REL_CYCLE",
    ),
    RelationType.RUN_RETRY_OF_RUN.value: RelationRule(
        "run",
        "run",
        1,
        None,
        "Run endpoints cannot be physically deleted",
        acyclic=True,
        require_source_newer=True,
        error_code="E_REL_RETRY_INVALID",
    ),
    RelationType.OBJECT_SUPERSEDES_OBJECT.value: RelationRule(
        "same_revisioned_type",
        "same_revisioned_type",
        1,
        None,
        "old object becomes superseded; no physical delete",
        acyclic=True,
        require_source_newer=True,
        error_code="E_REL_SUPERSEDE_INVALID",
    ),
}


REVISIONED_TYPES = frozenset(
    {"resource", "locator", "claim", "method", "finding", "decision"}
)


@dataclass(frozen=True, slots=True)
class RelationEndpoint:
    object_type: str
    object_id: UUID
    project_id: UUID | None
    inquiry_id: UUID | None = None
    direction: str | None = None
    resource_id: UUID | None = None
    producer_run_id: UUID | None = None
    state: str | None = None
    revision: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RelationValidationContext:
    outgoing_count: int = 0
    incoming_count: int = 0
    existing_edges: frozenset[tuple[UUID, UUID]] = frozenset()


class RelationContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


TERMINAL_RUN_STATES = frozenset(
    {
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
        "budget_exceeded",
        "orphaned",
    }
)


def _shape_matches(
    relation_type: str,
    rule: RelationRule,
    source_type: str,
    target_type: str,
) -> bool:
    if relation_type == RelationType.OBJECT_SUPERSEDES_OBJECT.value:
        return source_type == target_type and source_type in REVISIONED_TYPES
    return source_type == rule.source_type and target_type == rule.target_type


def _path_exists(
    start: UUID,
    target: UUID,
    edges: frozenset[tuple[UUID, UUID]],
) -> bool:
    adjacency: dict[UUID, set[UUID]] = {}
    for source, destination in edges:
        adjacency.setdefault(source, set()).add(destination)
    pending = [start]
    seen: set[UUID] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(adjacency.get(current, ()))
    return False


def validate_relation_shape(
    relation_type: str,
    source_type: str,
    target_type: str,
    *,
    evidence_direction: str | None = None,
) -> RelationRule:
    """Validate the type and direction portion before repository lookups."""

    rule = RELATION_REGISTRY.get(relation_type)
    if rule is None:
        raise RelationContractError("E_REL_UNKNOWN", relation_type)
    if not _shape_matches(relation_type, rule, source_type, target_type):
        raise RelationContractError(rule.error_code, "source/target type mismatch")
    if (
        rule.required_direction is not None
        and evidence_direction != rule.required_direction
    ):
        raise RelationContractError(
            rule.error_code,
            f"evidence direction must be {rule.required_direction}",
        )
    return rule


def validate_relation(
    relation_type: str,
    source: RelationEndpoint,
    target: RelationEndpoint,
    context: RelationValidationContext = RelationValidationContext(),
) -> RelationRule:
    """Validate all deterministic registry rules for a proposed relation."""

    rule = validate_relation_shape(
        relation_type,
        source.object_type,
        target.object_type,
        evidence_direction=source.direction,
    )
    if source.object_id == target.object_id:
        raise RelationContractError(rule.error_code, "self relation is invalid")
    if rule.outgoing_max is not None and context.outgoing_count >= rule.outgoing_max:
        raise RelationContractError(rule.error_code, "outgoing cardinality exceeded")
    if rule.incoming_max is not None and context.incoming_count >= rule.incoming_max:
        raise RelationContractError(rule.error_code, "incoming cardinality exceeded")
    if (
        rule.same_project
        and source.project_id is not None
        and target.project_id is not None
        and source.project_id != target.project_id
    ):
        raise RelationContractError(rule.error_code, "cross-project relation denied")
    if rule.same_inquiry and (
        source.inquiry_id is None
        or target.inquiry_id is None
        or source.inquiry_id != target.inquiry_id
    ):
        raise RelationContractError(rule.error_code, "Inquiry scope mismatch")

    if relation_type == RelationType.RESOURCE_CONTAINS_EVIDENCE.value:
        if target.resource_id != source.object_id:
            raise RelationContractError(
                rule.error_code, "Evidence locator resolves to another Resource"
            )
    elif relation_type == RelationType.RUN_PRODUCES_ARTIFACT.value:
        if (
            target.producer_run_id is not None
            and target.producer_run_id != source.object_id
        ):
            raise RelationContractError(
                rule.error_code, "Artifact already has another producer"
            )
    elif relation_type == RelationType.RUN_PRODUCES_FINDING.value:
        if source.state not in TERMINAL_RUN_STATES:
            raise RelationContractError(
                rule.error_code,
                "Finding producer must be a terminal Run",
            )
        if (
            target.producer_run_id is not None
            and target.producer_run_id != source.object_id
        ):
            raise RelationContractError(
                rule.error_code, "Finding already has another producer"
            )

    if rule.require_source_newer:
        if (
            source.created_at is None
            or target.created_at is None
            or source.created_at <= target.created_at
        ):
            raise RelationContractError(rule.error_code, "source must be newer")
        if relation_type == RelationType.OBJECT_SUPERSEDES_OBJECT.value and (
            source.revision is None
            or target.revision is None
            or source.revision <= target.revision
        ):
            raise RelationContractError(
                rule.error_code, "source revision must be newer"
            )

    if rule.acyclic and _path_exists(
        target.object_id, source.object_id, context.existing_edges
    ):
        raise RelationContractError(rule.error_code, "relation would create a cycle")
    return rule


def validate_minimum_cardinality(
    object_type: str,
    *,
    state: str,
    evidence_count: int = 0,
    terminal_run_count: int = 0,
    finding_count: int = 0,
) -> None:
    """Validate object-level minimums that require repository relation counts."""

    if min(evidence_count, terminal_run_count, finding_count) < 0:
        raise RelationContractError(
            "E_REL_INVALID",
            "relation counts cannot be negative",
        )
    if (
        object_type == "finding"
        and evidence_count == 0
        and terminal_run_count == 0
    ):
        raise RelationContractError(
            "E_REL_FINDING_EMPTY",
            "Finding requires Evidence or a terminal Run",
        )
    if object_type == "decision" and state == "confirmed" and finding_count == 0:
        raise RelationContractError(
            "E_REL_DECISION_EMPTY",
            "confirmed Decision requires at least one Finding",
        )
