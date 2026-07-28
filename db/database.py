"""v0.2.0-dev 遗留刷题存储；退役前必须支持已有数据导出或迁移。"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class ProblemRecord:
    id: int
    lc_number: int
    title: str
    difficulty: str
    pattern: str
    date_solved: str
    status: str
    notes: str
    created_at: str


def default_database_path() -> Path:
    """返回适合开发环境和打包应用的可写数据库路径。"""

    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / "Nana" / "nana.db"


class Database:
    DIFFICULTIES = ("Easy", "Medium", "Hard")
    STATUSES = ("AC", "待复习")

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_database_path()
        self._memory_connection: sqlite3.Connection | None = None
        if str(self.path) == ":memory:":
            self._memory_connection = sqlite3.connect(":memory:")
            self._configure_connection(self._memory_connection)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        connection = sqlite3.connect(self.path)
        self._configure_connection(connection)
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """提供会提交/回滚并可靠关闭的短连接。"""

        connection = self._connect()
        persistent = connection is self._memory_connection
        try:
            with connection:
                yield connection
        finally:
            if not persistent:
                connection.close()

    def close(self) -> None:
        """关闭内存数据库持有的长连接；文件数据库使用短连接无需处理。"""

        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS problems (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    lc_number   INTEGER NOT NULL UNIQUE,
                    title       TEXT NOT NULL,
                    difficulty  TEXT NOT NULL
                                CHECK(difficulty IN ('Easy','Medium','Hard')),
                    pattern     TEXT NOT NULL,
                    date_solved TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'AC'
                                CHECK(status IN ('AC','待复习')),
                    notes       TEXT NOT NULL DEFAULT '',
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_problems_pattern ON problems(pattern)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_problems_difficulty "
                "ON problems(difficulty)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_problems_date_solved "
                "ON problems(date_solved)"
            )

    @staticmethod
    def _validate(
        lc_number: int,
        title: str,
        difficulty: str,
        pattern: str,
        date_solved: str,
        status: str,
    ) -> None:
        if lc_number <= 0:
            raise ValueError("题号必须大于 0。")
        if not title.strip():
            raise ValueError("题名不能为空。")
        if difficulty not in Database.DIFFICULTIES:
            raise ValueError("难度必须是 Easy、Medium 或 Hard。")
        if not pattern.strip():
            raise ValueError("所属模式不能为空。")
        if status not in Database.STATUSES:
            raise ValueError("状态必须是 AC 或待复习。")
        try:
            date.fromisoformat(date_solved)
        except ValueError as error:
            raise ValueError("日期必须使用 YYYY-MM-DD 格式。") from error

    def add_problem(
        self,
        *,
        lc_number: int,
        title: str,
        difficulty: str,
        pattern: str,
        date_solved: str,
        status: str = "AC",
        notes: str = "",
    ) -> int:
        self._validate(
            lc_number, title, difficulty, pattern, date_solved, status
        )
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO problems (
                    lc_number, title, difficulty, pattern,
                    date_solved, status, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lc_number,
                    title.strip(),
                    difficulty,
                    pattern.strip(),
                    date_solved,
                    status,
                    notes.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def delete_problem(self, record_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM problems WHERE id = ?",
                (record_id,),
            )
            return cursor.rowcount > 0

    def list_problems(
        self,
        *,
        pattern: str | None = None,
        difficulty: str | None = None,
        newest_first: bool = True,
    ) -> list[ProblemRecord]:
        clauses: list[str] = []
        parameters: list[str] = []
        if pattern:
            clauses.append("pattern = ?")
            parameters.append(pattern)
        if difficulty:
            clauses.append("difficulty = ?")
            parameters.append(difficulty)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if newest_first else "ASC"
        query = (
            "SELECT id, lc_number, title, difficulty, pattern, date_solved, "
            "status, notes, created_at FROM problems "
            f"{where} ORDER BY date_solved {direction}, lc_number ASC"
        )
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [ProblemRecord(**dict(row)) for row in rows]

    def total_count(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM problems"
            ).fetchone()
        return int(row["count"])

    def difficulty_counts(self) -> dict[str, int]:
        counts = {difficulty: 0 for difficulty in self.DIFFICULTIES}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT difficulty, COUNT(*) AS count "
                "FROM problems GROUP BY difficulty"
            ).fetchall()
        counts.update({str(row["difficulty"]): int(row["count"]) for row in rows})
        return counts

    def pattern_counts(self) -> dict[str, int]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT pattern, COUNT(*) AS count "
                "FROM problems GROUP BY pattern "
                "ORDER BY count DESC, pattern ASC"
            ).fetchall()
        return {str(row["pattern"]): int(row["count"]) for row in rows}
