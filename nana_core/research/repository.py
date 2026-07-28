"""研究对象的 SQLite 持久化；不依赖 PySide6 或模型供应商。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import astuple
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from nana_core.research.models import (
    Claim,
    Evidence,
    Experiment,
    Insight,
    Method,
    ResearchThread,
    Source,
)


SCHEMA_VERSION = 2
THREAD_STATUSES = ("inbox", "active", "blocked", "completed", "archived")
SOURCE_TYPES = ("paper", "project", "code", "dataset", "blog", "case")
AI_PERMISSIONS = ("undecided", "allowed", "denied")
EVIDENCE_TYPES = ("text", "code", "data", "experiment")
VERIFICATION_STATUSES = ("pending", "verified", "unsupported")
CONFIDENCE_LEVELS = ("low", "medium", "high")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label}不能为空。")
    return cleaned


class ResearchRepository:
    """维护七类研究对象及其线程边界。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._memory_connection: sqlite3.Connection | None = None
        if str(self.path) == ":memory:":
            self._memory_connection = sqlite3.connect(":memory:")
            self._configure(self._memory_connection)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _configure(connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        connection = sqlite3.connect(self.path)
        self._configure(connection)
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        persistent = connection is self._memory_connection
        try:
            with connection:
                yield connection
        finally:
            if not persistent:
                connection.close()

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS nana_schema_versions (
                    component TEXT PRIMARY KEY,
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    question TEXT NOT NULL,
                    scope_exclusions TEXT NOT NULL DEFAULT '',
                    completion_criteria TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK (
                        status IN ('inbox','active','blocked','completed','archived')
                    ),
                    next_step TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_sources (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES research_threads(id)
                        ON DELETE RESTRICT,
                    source_type TEXT NOT NULL CHECK (
                        source_type IN (
                            'paper','project','code','dataset','blog','case'
                        )
                    ),
                    title TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '',
                    selection_reason TEXT NOT NULL DEFAULT '',
                    ai_permission TEXT NOT NULL CHECK (
                        ai_permission IN ('undecided','allowed','denied')
                    ),
                    legacy_record_id INTEGER UNIQUE,
                    legacy_metadata TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_claims (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES research_threads(id)
                        ON DELETE RESTRICT,
                    source_id TEXT NOT NULL REFERENCES research_sources(id)
                        ON DELETE RESTRICT,
                    statement TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_methods (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES research_threads(id)
                        ON DELETE RESTRICT,
                    name TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    mechanism TEXT NOT NULL,
                    assumptions TEXT NOT NULL DEFAULT '',
                    applicability TEXT NOT NULL DEFAULT '',
                    failure_boundaries TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_evidence (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES research_threads(id)
                        ON DELETE RESTRICT,
                    source_id TEXT NOT NULL REFERENCES research_sources(id)
                        ON DELETE RESTRICT,
                    claim_id TEXT NOT NULL REFERENCES research_claims(id)
                        ON DELETE RESTRICT,
                    locator TEXT NOT NULL,
                    evidence_type TEXT NOT NULL CHECK (
                        evidence_type IN ('text','code','data','experiment')
                    ),
                    content TEXT NOT NULL,
                    verification_status TEXT NOT NULL CHECK (
                        verification_status IN ('pending','verified','unsupported')
                    ),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_experiments (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES research_threads(id)
                        ON DELETE RESTRICT,
                    method_id TEXT NOT NULL REFERENCES research_methods(id)
                        ON DELETE RESTRICT,
                    title TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    environment TEXT NOT NULL DEFAULT '',
                    inputs TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    limitations TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_insights (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES research_threads(id)
                        ON DELETE RESTRICT,
                    method_id TEXT NOT NULL REFERENCES research_methods(id)
                        ON DELETE RESTRICT,
                    statement TEXT NOT NULL,
                    confidence TEXT NOT NULL CHECK (
                        confidence IN ('low','medium','high')
                    ),
                    next_action TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sources_thread
                    ON research_sources(thread_id);
                CREATE INDEX IF NOT EXISTS idx_claims_thread
                    ON research_claims(thread_id);
                CREATE INDEX IF NOT EXISTS idx_methods_thread
                    ON research_methods(thread_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_thread
                    ON research_evidence(thread_id);
                CREATE INDEX IF NOT EXISTS idx_experiments_thread
                    ON research_experiments(thread_id);
                CREATE INDEX IF NOT EXISTS idx_insights_thread
                    ON research_insights(thread_id);
                """
            )
            row = connection.execute(
                "SELECT version FROM nana_schema_versions WHERE component = ?",
                ("research",),
            ).fetchone()
            if row is not None and int(row["version"]) > SCHEMA_VERSION:
                raise RuntimeError("研究数据库来自更高版本，当前程序不能安全打开。")
            source_columns = {
                str(column["name"])
                for column in connection.execute(
                    "PRAGMA table_info(research_sources)"
                ).fetchall()
            }
            if "legacy_record_id" not in source_columns:
                connection.execute(
                    "ALTER TABLE research_sources ADD COLUMN legacy_record_id INTEGER"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_legacy_record "
                    "ON research_sources(legacy_record_id)"
                )
            if "legacy_metadata" not in source_columns:
                connection.execute(
                    "ALTER TABLE research_sources ADD COLUMN "
                    "legacy_metadata TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                """
                INSERT INTO nana_schema_versions(component, version)
                VALUES ('research', ?)
                ON CONFLICT(component) DO UPDATE SET version = excluded.version
                """,
                (SCHEMA_VERSION,),
            )

    @staticmethod
    def _new_id() -> str:
        return str(uuid4())

    @staticmethod
    def _choice(value: str, choices: tuple[str, ...], label: str) -> str:
        if value not in choices:
            raise ValueError(f"{label}必须是：{', '.join(choices)}。")
        return value

    def _thread_exists(self, connection: sqlite3.Connection, thread_id: str) -> None:
        row = connection.execute(
            "SELECT 1 FROM research_threads WHERE id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"研究线程不存在：{thread_id}")

    @staticmethod
    def _related_thread(
        connection: sqlite3.Connection,
        table: str,
        item_id: str,
        expected_thread_id: str,
        label: str,
    ) -> None:
        row = connection.execute(
            f"SELECT thread_id FROM {table} WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"{label}不存在：{item_id}")
        if row["thread_id"] != expected_thread_id:
            raise ValueError(f"{label}与目标研究线程不一致。")

    def create_thread(
        self,
        *,
        title: str,
        question: str,
        scope_exclusions: str = "",
        completion_criteria: str = "",
        status: str = "inbox",
        next_step: str = "",
    ) -> ResearchThread:
        status = self._choice(status, THREAD_STATUSES, "线程状态")
        item = ResearchThread(
            id=self._new_id(),
            title=_required(title, "线程标题"),
            question=_required(question, "研究问题"),
            scope_exclusions=scope_exclusions.strip(),
            completion_criteria=completion_criteria.strip(),
            status=status,
            next_step=next_step.strip(),
            created_at=_now(),
            updated_at=_now(),
        )
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO research_threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                astuple(item),
            )
        return item

    def create_source(
        self,
        thread_id: str,
        *,
        source_type: str,
        title: str,
        locator: str,
        version: str = "",
        selection_reason: str = "",
        ai_permission: str = "undecided",
        legacy_record_id: int | None = None,
        legacy_metadata: str = "",
    ) -> Source:
        source_type = self._choice(source_type, SOURCE_TYPES, "来源类型")
        ai_permission = self._choice(ai_permission, AI_PERMISSIONS, "AI 权限")
        item = Source(
            self._new_id(),
            thread_id,
            source_type,
            _required(title, "来源标题"),
            _required(locator, "来源位置"),
            version.strip(),
            selection_reason.strip(),
            ai_permission,
            legacy_record_id,
            legacy_metadata,
            _now(),
        )
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            connection.execute(
                """
                INSERT INTO research_sources (
                    id, thread_id, source_type, title, locator, version,
                    selection_reason, ai_permission, legacy_record_id,
                    legacy_metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                astuple(item),
            )
        return item

    def create_claim(
        self, thread_id: str, source_id: str, *, statement: str
    ) -> Claim:
        item = Claim(
            self._new_id(), thread_id, source_id, _required(statement, "主张"), _now()
        )
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            self._related_thread(
                connection, "research_sources", source_id, thread_id, "来源"
            )
            connection.execute(
                "INSERT INTO research_claims VALUES (?, ?, ?, ?, ?)",
                astuple(item),
            )
        return item

    def create_method(
        self,
        thread_id: str,
        *,
        name: str,
        problem: str,
        mechanism: str,
        assumptions: str = "",
        applicability: str = "",
        failure_boundaries: str = "",
    ) -> Method:
        item = Method(
            self._new_id(),
            thread_id,
            _required(name, "方法名称"),
            _required(problem, "方法解决的问题"),
            _required(mechanism, "方法机制"),
            assumptions.strip(),
            applicability.strip(),
            failure_boundaries.strip(),
            _now(),
        )
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            connection.execute(
                "INSERT INTO research_methods VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                astuple(item),
            )
        return item

    def create_evidence(
        self,
        thread_id: str,
        source_id: str,
        claim_id: str,
        *,
        locator: str,
        evidence_type: str,
        content: str,
        verification_status: str = "pending",
    ) -> Evidence:
        evidence_type = self._choice(evidence_type, EVIDENCE_TYPES, "证据类型")
        verification_status = self._choice(
            verification_status, VERIFICATION_STATUSES, "核对状态"
        )
        item = Evidence(
            self._new_id(),
            thread_id,
            source_id,
            claim_id,
            _required(locator, "证据位置"),
            evidence_type,
            _required(content, "证据内容"),
            verification_status,
            _now(),
        )
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            self._related_thread(
                connection, "research_sources", source_id, thread_id, "来源"
            )
            self._related_thread(
                connection, "research_claims", claim_id, thread_id, "主张"
            )
            claim = connection.execute(
                "SELECT source_id FROM research_claims WHERE id = ?", (claim_id,)
            ).fetchone()
            if claim["source_id"] != source_id:
                raise ValueError("证据来源与主张来源不一致。")
            connection.execute(
                """
                INSERT INTO research_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                astuple(item),
            )
        return item

    def create_experiment(
        self,
        thread_id: str,
        method_id: str,
        *,
        title: str,
        purpose: str,
        environment: str = "",
        inputs: str = "",
        result: str = "",
        limitations: str = "",
    ) -> Experiment:
        item = Experiment(
            self._new_id(),
            thread_id,
            method_id,
            _required(title, "实验标题"),
            _required(purpose, "实验目的"),
            environment.strip(),
            inputs.strip(),
            result.strip(),
            limitations.strip(),
            _now(),
        )
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            self._related_thread(
                connection, "research_methods", method_id, thread_id, "方法"
            )
            connection.execute(
                """
                INSERT INTO research_experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                astuple(item),
            )
        return item

    def create_insight(
        self,
        thread_id: str,
        method_id: str,
        *,
        statement: str,
        confidence: str = "low",
        next_action: str = "",
    ) -> Insight:
        confidence = self._choice(confidence, CONFIDENCE_LEVELS, "置信度")
        item = Insight(
            self._new_id(),
            thread_id,
            method_id,
            _required(statement, "个人判断"),
            confidence,
            next_action.strip(),
            _now(),
        )
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            self._related_thread(
                connection, "research_methods", method_id, thread_id, "方法"
            )
            connection.execute(
                "INSERT INTO research_insights VALUES (?, ?, ?, ?, ?, ?, ?)",
                astuple(item),
            )
        return item

    def get_thread(self, thread_id: str) -> ResearchThread | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM research_threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return ResearchThread(**dict(row)) if row is not None else None

    def get_source_by_legacy_record(self, record_id: int) -> Source | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM research_sources WHERE legacy_record_id = ?",
                (record_id,),
            ).fetchone()
        return Source(**dict(row)) if row is not None else None

    def list_threads(self) -> list[ResearchThread]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM research_threads ORDER BY updated_at DESC, id"
            ).fetchall()
        return [ResearchThread(**dict(row)) for row in rows]

    def update_thread_status(
        self,
        thread_id: str,
        status: str,
        *,
        next_step: str | None = None,
    ) -> ResearchThread:
        status = self._choice(status, THREAD_STATUSES, "线程状态")
        updated_at = _now()
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            if next_step is None:
                connection.execute(
                    """
                    UPDATE research_threads
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, updated_at, thread_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE research_threads
                    SET status = ?, next_step = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, next_step.strip(), updated_at, thread_id),
                )
        thread = self.get_thread(thread_id)
        if thread is None:
            raise RuntimeError("更新后无法重新读取研究线程。")
        return thread

    def list_for_thread(self, model: type, thread_id: str) -> list:
        mapping = {
            Source: ("research_sources", Source),
            Claim: ("research_claims", Claim),
            Evidence: ("research_evidence", Evidence),
            Method: ("research_methods", Method),
            Experiment: ("research_experiments", Experiment),
            Insight: ("research_insights", Insight),
        }
        if model not in mapping:
            raise ValueError("不支持的研究对象类型。")
        table, constructor = mapping[model]
        with self._connection() as connection:
            self._thread_exists(connection, thread_id)
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE thread_id = ? ORDER BY created_at, id",
                (thread_id,),
            ).fetchall()
        return [constructor(**dict(row)) for row in rows]
