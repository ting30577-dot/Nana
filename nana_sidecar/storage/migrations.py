"""Ordered, append-only schema migration registry."""

from __future__ import annotations

from dataclasses import dataclass

from nana_sidecar.storage.schema import (
    SCHEMA_V1_HASH,
    SCHEMA_V1_SQL,
    SCHEMA_V2_HASH,
    SCHEMA_V2_SQL,
    SCHEMA_V3_HASH,
    SCHEMA_V3_SQL,
    SCHEMA_V4_HASH,
    SCHEMA_V4_SQL,
    SCHEMA_V5_HASH,
    SCHEMA_V5_SQL,
    SCHEMA_V6_HASH,
    SCHEMA_V6_SQL,
    SCHEMA_V7_HASH,
    SCHEMA_V7_SQL,
)


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str
    contract_hash: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="0001_contract_kernel",
        sql=SCHEMA_V1_SQL,
        contract_hash=SCHEMA_V1_HASH,
    ),
    Migration(
        version=2,
        name="0002_d2_00_hardening",
        sql=SCHEMA_V2_SQL,
        contract_hash=SCHEMA_V2_HASH,
    ),
    Migration(
        version=3,
        name="0003_d2_01_action_cancelled_event",
        sql=SCHEMA_V3_SQL,
        contract_hash=SCHEMA_V3_HASH,
    ),
    Migration(
        version=4,
        name="0004_d2_03a_full_capability_registry",
        sql=SCHEMA_V4_SQL,
        contract_hash=SCHEMA_V4_HASH,
    ),
    Migration(
        version=5,
        name="0005_d2_05_run_budget_ledger",
        sql=SCHEMA_V5_SQL,
        contract_hash=SCHEMA_V5_HASH,
    ),
    Migration(
        version=6,
        name="0006_d2_final_authorization_material",
        sql=SCHEMA_V6_SQL,
        contract_hash=SCHEMA_V6_HASH,
    ),
    Migration(
        version=7,
        name="0007_d3_07_approval_and_external_write_fence",
        sql=SCHEMA_V7_SQL,
        contract_hash=SCHEMA_V7_HASH,
    ),
)


def migrations_after(version: int, target: int) -> tuple[Migration, ...]:
    if version < 0 or target < version:
        raise ValueError("migration versions must move forward")
    selected = tuple(
        migration
        for migration in MIGRATIONS
        if version < migration.version <= target
    )
    expected = tuple(range(version + 1, target + 1))
    if tuple(migration.version for migration in selected) != expected:
        raise RuntimeError(
            f"migration registry has a gap between {version} and {target}"
        )
    return selected
