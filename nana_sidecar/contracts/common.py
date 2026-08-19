"""Shared strict value objects for the sidecar contract."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Identifier = UUID
Revision = Annotated[int, Field(ge=1)]
JsonObject = dict[str, Any]
HashDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class ContractModel(BaseModel):
    """Strict base model used by every externally visible contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ActorKind(StrEnum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL = "tool"


class DataClass(StrEnum):
    PUBLIC = "public"
    PERSONAL = "personal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"


class RiskTier(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"


class ActorRef(ContractModel):
    kind: ActorKind
    id: str | None = Field(default=None, min_length=1, max_length=128)
    version: str | None = Field(default=None, min_length=1, max_length=128)


class VersionedRef(ContractModel):
    id: Annotated[str, Field(min_length=1, max_length=160)]
    version: Annotated[str, Field(min_length=1, max_length=128)]
    digest: HashDigest | None = None


class CapabilityRef(ContractModel):
    """Executable Capability identity pinned to an implementation digest."""

    id: Annotated[str, Field(min_length=1, max_length=160)]
    version: Annotated[str, Field(min_length=1, max_length=128)]
    digest: HashDigest


class BudgetSnapshot(ContractModel):
    """Immutable limits frozen when a Run or authorization is created."""

    wall_clock_seconds: int = Field(gt=0)
    cpu_seconds: int | None = Field(default=None, gt=0)
    memory_bytes: int | None = Field(default=None, gt=0)
    gpu_seconds: int | None = Field(default=None, gt=0)
    max_actions: int = Field(gt=0)
    max_concurrency: int = Field(gt=0)
    max_model_calls: int = Field(ge=0)
    max_model_tokens: int = Field(ge=0)
    max_cost_micros: int = Field(ge=0)
    max_retries: int = Field(ge=0)
    max_output_bytes: int = Field(gt=0)
    max_artifact_bytes: int = Field(gt=0)
    max_download_bytes: int = Field(ge=0)
    network_targets: tuple[str, ...] = ()
    read_roots: tuple[str, ...] = ()
    write_roots: tuple[str, ...] = ()


class EffectScope(ContractModel):
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    network: tuple[str, ...] = ()
    processes: tuple[str, ...] = ()


class ResourceUsage(ContractModel):
    wall_clock_ms: int = Field(ge=0)
    cpu_ms: int | None = Field(default=None, ge=0)
    peak_memory_bytes: int | None = Field(default=None, ge=0)
    model_tokens: int = Field(default=0, ge=0)
    cost_micros: int = Field(default=0, ge=0)
    output_bytes: int = Field(default=0, ge=0)
    artifact_bytes: int = Field(default=0, ge=0)


class Timestamped(ContractModel):
    created_at: datetime


def normalize_utc_datetime(value: datetime) -> datetime:
    """Reject naive datetimes and normalize aware values to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("authorization timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def effect_scope_is_subset(actual: EffectScope, authorized: EffectScope) -> bool:
    """Return whether every observed effect was explicitly authorized."""

    return (
        set(actual.reads).issubset(authorized.reads)
        and set(actual.writes).issubset(authorized.writes)
        and set(actual.network).issubset(authorized.network)
        and set(actual.processes).issubset(authorized.processes)
    )
