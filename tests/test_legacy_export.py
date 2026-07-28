"""遗留刷题数据 JSON 归档的安全性与完整性测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from db.database import Database
from db.legacy_export import (
    LegacyArchiveError,
    SCHEMA_VERSION,
    export_legacy_problems,
    load_legacy_archive,
)


class LegacyExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database = Database(self.root / "nana.db")
        self.database.add_problem(
            lc_number=167,
            title="两数之和 II",
            difficulty="Medium",
            pattern="双指针",
            date_solved="2026-07-26",
            status="待复习",
            notes="保留全部原始字段。",
        )
        self.archive_path = self.root / "archives" / "legacy.json"

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_export_is_lossless_and_can_be_loaded_again(self) -> None:
        exported_at = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)

        archive = export_legacy_problems(
            self.database,
            self.archive_path,
            exported_at=exported_at,
        )
        loaded = load_legacy_archive(self.archive_path)

        self.assertEqual(archive, loaded)
        self.assertEqual(loaded.schema_version, SCHEMA_VERSION)
        self.assertEqual(loaded.exported_at, "2026-07-27T08:30:00Z")
        self.assertEqual(loaded.record_count, self.database.total_count())
        self.assertEqual(
            loaded.records[0],
            {
                "id": 1,
                "lc_number": 167,
                "title": "两数之和 II",
                "difficulty": "Medium",
                "pattern": "双指针",
                "date_solved": "2026-07-26",
                "status": "待复习",
                "notes": "保留全部原始字段。",
                "created_at": loaded.records[0]["created_at"],
            },
        )

    def test_export_does_not_overwrite_existing_archive_by_default(self) -> None:
        self.archive_path.parent.mkdir(parents=True)
        self.archive_path.write_text("原有文件", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            export_legacy_problems(self.database, self.archive_path)

        self.assertEqual(self.archive_path.read_text(encoding="utf-8"), "原有文件")
        self.assertEqual(self.database.total_count(), 1)

    def test_tampered_record_fails_digest_verification(self) -> None:
        export_legacy_problems(self.database, self.archive_path)
        payload = json.loads(self.archive_path.read_text(encoding="utf-8"))
        payload["records"][0]["notes"] = "内容被修改"
        self.archive_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(LegacyArchiveError, "摘要校验失败"):
            load_legacy_archive(self.archive_path)

        self.assertEqual(self.database.total_count(), 1)

    def test_mismatched_record_count_is_rejected(self) -> None:
        export_legacy_problems(self.database, self.archive_path)
        payload = json.loads(self.archive_path.read_text(encoding="utf-8"))
        payload["record_count"] = 2
        self.archive_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(LegacyArchiveError, "记录数"):
            load_legacy_archive(self.archive_path)

    def test_naive_export_time_is_rejected_without_writing(self) -> None:
        with self.assertRaisesRegex(ValueError, "时区"):
            export_legacy_problems(
                self.database,
                self.archive_path,
                exported_at=datetime(2026, 7, 27, 8, 30),
            )

        self.assertFalse(self.archive_path.exists())
        self.assertEqual(self.database.total_count(), 1)


if __name__ == "__main__":
    unittest.main()
