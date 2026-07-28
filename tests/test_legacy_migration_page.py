"""遗留数据迁移页的无损归档交互测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from db.database import Database  # noqa: E402
from db.legacy_export import load_legacy_archive  # noqa: E402
from nana_core.research import ResearchRepository, Source  # noqa: E402
from ui.legacy_migration_page import LegacyMigrationPage  # noqa: E402


class LegacyMigrationPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database = Database(self.root / "nana.db")
        self.repository = ResearchRepository(self.database.path)
        self.page = LegacyMigrationPage(self.database, self.repository)

    def tearDown(self) -> None:
        self.page.close()
        self.repository.close()
        self.database.close()
        self.temp_directory.cleanup()

    def test_empty_database_disables_export(self) -> None:
        self.assertIn("0 条", self.page.count_label.text())
        self.assertFalse(self.page.export_button.isEnabled())

    def test_export_archives_all_records_without_modifying_database(self) -> None:
        self.database.add_problem(
            lc_number=167,
            title="两数之和 II",
            difficulty="Medium",
            pattern="双指针",
            date_solved="2026-07-27",
            notes="遗留记录",
        )
        self.page.refresh()
        archive_path = self.root / "legacy.json"

        with patch("ui.legacy_migration_page.QMessageBox.information"):
            succeeded = self.page.export_to(archive_path)

        self.assertTrue(succeeded)
        self.assertEqual(load_legacy_archive(archive_path).record_count, 1)
        self.assertEqual(self.database.total_count(), 1)
        self.assertEqual(self.page.last_archive_path, archive_path)

    def test_selected_record_migrates_only_after_verified_archive(self) -> None:
        self.database.add_problem(
            lc_number=167,
            title="两数之和 II",
            difficulty="Medium",
            pattern="双指针",
            date_solved="2026-07-27",
            notes="保留为案例",
        )
        thread = self.repository.create_thread(
            title="碰撞指针研究", question="单调排除为什么成立？"
        )
        self.page.refresh()
        archive_path = self.root / "legacy.json"
        with patch("ui.legacy_migration_page.QMessageBox.information"):
            self.assertTrue(self.page.export_to(archive_path))
        self.page.records_table.item(0, 0).setCheckState(
            Qt.CheckState.Checked
        )

        with patch("ui.legacy_migration_page.QMessageBox.information"):
            self.page.migrate_selected()

        sources = self.repository.list_for_thread(Source, thread.id)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_type, "case")
        self.assertEqual(sources[0].legacy_record_id, 1)
        self.assertIn('"notes":"保留为案例"', sources[0].legacy_metadata)
        self.assertEqual(self.database.total_count(), 1)

    def test_existing_file_is_not_overwritten(self) -> None:
        self.database.add_problem(
            lc_number=704,
            title="二分查找",
            difficulty="Easy",
            pattern="二分查找",
            date_solved="2026-07-27",
        )
        path = self.root / "existing.json"
        path.write_text("保留原文件", encoding="utf-8")

        with patch("ui.legacy_migration_page.QMessageBox.warning") as warning:
            succeeded = self.page.export_to(path)

        self.assertFalse(succeeded)
        warning.assert_called_once()
        self.assertEqual(path.read_text(encoding="utf-8"), "保留原文件")
        self.assertEqual(self.database.total_count(), 1)


if __name__ == "__main__":
    unittest.main()
