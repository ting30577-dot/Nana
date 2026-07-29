"""SQLite schema inspection and migration runner for vNext."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nana_sidecar import SCHEMA_READ_CEILING, SCHEMA_VERSION
from nana_sidecar.storage.migrations import Migration, migrations_after


class SchemaTooNewError(RuntimeError):
    pass


class IncompatibleDatabaseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    current_version: int
    target_version: int
    steps: tuple[Migration, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _configure(connection: sqlite3.Connection) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")


def _user_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _current_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _validate_existing_schema(
    connection: sqlite3.Connection,
    current: int,
    user_tables: set[str],
) -> None:
    if current > SCHEMA_READ_CEILING:
        raise SchemaTooNewError(
            f"schema version {current} exceeds read ceiling "
            f"{SCHEMA_READ_CEILING}"
        )
    if current == 0:
        if user_tables:
            raise IncompatibleDatabaseError(
                "refusing to initialize vNext schema in a non-empty "
                "unversioned database"
            )
        return
    required = {"schema_metadata", "migration_history"}
    if not required <= user_tables:
        raise IncompatibleDatabaseError(
            "versioned database is missing vNext schema markers"
        )
    marker = connection.execute(
        "SELECT value FROM schema_metadata WHERE key = ?",
        ("schema_version",),
    ).fetchone()
    if marker is None or int(marker["value"]) != current:
        raise IncompatibleDatabaseError(
            "schema marker does not match SQLite user_version"
        )
    history = connection.execute(
        "SELECT version, contract_hash FROM migration_history "
        "ORDER BY version"
    ).fetchall()
    if tuple(int(row["version"]) for row in history) != tuple(
        range(1, current + 1)
    ):
        raise IncompatibleDatabaseError("migration history is incomplete")
    expected = migrations_after(0, current)
    actual_hashes = tuple(str(row["contract_hash"]) for row in history)
    if actual_hashes != tuple(step.contract_hash for step in expected):
        raise IncompatibleDatabaseError("migration contract hash mismatch")


def _open(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(path))
    _configure(connection)
    return connection


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open and verify a previously initialized vNext database."""

    connection = _open(path)
    try:
        current = _current_version(connection)
        _validate_existing_schema(
            connection,
            current,
            _user_tables(connection),
        )
        if current == 0:
            raise IncompatibleDatabaseError("vNext database is not initialized")
    except Exception:
        connection.close()
        raise
    return connection


def plan_database_migrations(
    path: str | Path,
    *,
    target_version: int = SCHEMA_VERSION,
) -> MigrationPlan:
    """Inspect migration work without changing the database or its parent."""

    target = Path(path)
    if target_version > SCHEMA_READ_CEILING:
        raise SchemaTooNewError(
            f"target schema {target_version} exceeds read ceiling "
            f"{SCHEMA_READ_CEILING}"
        )
    if not target.exists() or target.stat().st_size == 0:
        current = 0
    else:
        uri = f"{target.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        _configure(connection)
        try:
            current = _current_version(connection)
            _validate_existing_schema(connection, current, _user_tables(connection))
        finally:
            connection.close()
    return MigrationPlan(
        current_version=current,
        target_version=target_version,
        steps=migrations_after(current, target_version),
    )


def _apply_migration(connection: sqlite3.Connection, migration: Migration) -> None:
    applied_at = _now().replace("'", "''")
    name = migration.name.replace("'", "''")
    contract_hash = migration.contract_hash.replace("'", "''")
    script = (
        "BEGIN IMMEDIATE;\n"
        f"{migration.sql}\n"
        "INSERT INTO migration_history(version, name, contract_hash, applied_at) "
        f"VALUES ({migration.version}, '{name}', '{contract_hash}', "
        f"'{applied_at}');\n"
        "INSERT INTO schema_metadata(key, value) "
        f"VALUES ('schema_version', '{migration.version}') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value;\n"
        f"PRAGMA user_version = {migration.version};\n"
        "COMMIT;\n"
    )
    try:
        connection.executescript(script)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def initialize_database(path: str | Path) -> sqlite3.Connection:
    """Apply all pending migrations and return a verified WAL connection."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = _open(target)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        current = _current_version(connection)
        _validate_existing_schema(connection, current, _user_tables(connection))
        for migration in migrations_after(current, SCHEMA_VERSION):
            _apply_migration(connection, migration)
        _validate_existing_schema(
            connection,
            _current_version(connection),
            _user_tables(connection),
        )
    except Exception:
        connection.close()
        raise
    return connection
