"""v0.2.0-alpha 的最小研究领域对象。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResearchThread:
    id: str
    title: str
    question: str
    scope_exclusions: str
    completion_criteria: str
    status: str
    next_step: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    thread_id: str
    source_type: str
    title: str
    locator: str
    version: str
    selection_reason: str
    ai_permission: str
    legacy_record_id: int | None
    legacy_metadata: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    thread_id: str
    source_id: str
    statement: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    thread_id: str
    source_id: str
    claim_id: str
    locator: str
    evidence_type: str
    content: str
    verification_status: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Method:
    id: str
    thread_id: str
    name: str
    problem: str
    mechanism: str
    assumptions: str
    applicability: str
    failure_boundaries: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Experiment:
    id: str
    thread_id: str
    method_id: str
    title: str
    purpose: str
    environment: str
    inputs: str
    result: str
    limitations: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Insight:
    id: str
    thread_id: str
    method_id: str
    statement: str
    confidence: str
    next_action: str
    created_at: str
