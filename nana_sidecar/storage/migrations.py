"""Ordered, append-only schema migration registry."""

from __future__ import annotations

from dataclasses import dataclass

from nana_sidecar.storage.schema import SCHEMA_V1_HASH, SCHEMA_V1_SQL


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
