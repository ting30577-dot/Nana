"""迁移期遗留刷题数据的 SQLite 持久化测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from db.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_directory.name) / "tracker.db"
        self.database = Database(self.path)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_add_reopen_filter_and_delete(self) -> None:
        record_id = self.database.add_problem(
            lc_number=167,
            title="两数之和 II",
            difficulty="Medium",
            pattern="双指针",
            date_solved="2026-07-26",
            notes="利用有序性排除一端。",
        )

        reopened = Database(self.path)
        records = reopened.list_problems(pattern="双指针")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].lc_number, 167)
        self.assertEqual(reopened.pattern_counts(), {"双指针": 1})

        self.assertTrue(reopened.delete_problem(record_id))
        self.assertEqual(reopened.total_count(), 0)

    def test_duplicate_problem_number_is_rejected(self) -> None:
        values = {
            "lc_number": 704,
            "title": "二分查找",
            "difficulty": "Easy",
            "pattern": "二分查找",
            "date_solved": "2026-07-26",
        }
        self.database.add_problem(**values)

        with self.assertRaises(sqlite3.IntegrityError):
            self.database.add_problem(**values)

    def test_attempting_status_is_not_allowed(self) -> None:
        with self.assertRaises(ValueError):
            self.database.add_problem(
                lc_number=1,
                title="两数之和",
                difficulty="Easy",
                pattern="其他",
                date_solved="2026-07-26",
                status="尝试中",
            )

    def test_in_memory_database_keeps_schema_across_operations(self) -> None:
        database = Database(":memory:")
        self.addCleanup(database.close)

        database.add_problem(
            lc_number=42,
            title="接雨水",
            difficulty="Hard",
            pattern="单调栈",
            date_solved="2026-07-27",
        )

        self.assertEqual(database.total_count(), 1)
        self.assertEqual(database.list_problems()[0].lc_number, 42)


if __name__ == "__main__":
    unittest.main()
