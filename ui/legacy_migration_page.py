"""遗留刷题数据的只读检测与无损归档入口。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from db.database import Database
from db.legacy_export import LegacyArchiveError, export_legacy_problems
from nana_core.research import ResearchRepository
from nana_core.research.legacy_migration import migrate_legacy_records


class LegacyMigrationPage(QWidget):
    """只允许检测和归档，不再新增、统计或删除刷题记录。"""

    def __init__(
        self,
        database: Database,
        repository: ResearchRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.repository = repository
        self.last_archive_path: Path | None = None

        title = QLabel("遗留数据迁移")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "旧刷题账本已退出产品路线。这里仅用于检查并无损归档已有记录。"
        )
        subtitle.setObjectName("mutedText")

        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(10)

        self.count_label = QLabel()
        self.count_label.setObjectName("statValue")
        self.explanation_label = QLabel()
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setObjectName("mutedText")
        self.archive_status = QLabel("尚未在本次运行中创建归档。")
        self.archive_status.setWordWrap(True)
        self.archive_status.setObjectName("mutedText")
        self.export_button = QPushButton("导出无损 JSON 归档")
        self.export_button.clicked.connect(self.choose_and_export)

        action_row = QHBoxLayout()
        action_row.addWidget(self.export_button)
        action_row.addStretch(1)

        card_layout.addWidget(self.count_label)
        card_layout.addWidget(self.explanation_label)
        card_layout.addSpacing(6)
        card_layout.addLayout(action_row)
        card_layout.addWidget(self.archive_status)

        self.target_thread = QComboBox()
        self.migrate_button = QPushButton("迁移选中记录为 case Source")
        self.migrate_button.clicked.connect(self.migrate_selected)
        migration_row = QHBoxLayout()
        migration_row.addWidget(QLabel("目标研究线程"))
        migration_row.addWidget(self.target_thread, 1)
        migration_row.addWidget(self.migrate_button)

        self.records_table = QTableWidget(0, 4)
        self.records_table.setHorizontalHeaderLabels(("选择", "题号", "题名", "日期"))
        self.records_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.horizontalHeader().setStretchLastSection(True)

        safety = QLabel(
            "安全规则：归档包含 schema_version、UTC 时间、全部原字段和 SHA-256 "
            "摘要；写入后会立即重新读取校验。失败时不修改数据库，也不移除原表。"
        )
        safety.setWordWrap(True)
        safety.setObjectName("mutedText")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(card)
        layout.addLayout(migration_row)
        layout.addWidget(self.records_table)
        layout.addWidget(safety)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        count = self.database.total_count()
        self.count_label.setText(f"检测到 {count} 条遗留刷题记录")
        if count:
            self.explanation_label.setText(
                "这些记录不会被自动转换成研究成果。请先保存归档；后续可选择"
                "其中真正有研究价值的案例，迁移为某个 Research Thread 的 Source。"
            )
            self.export_button.setEnabled(True)
        else:
            self.explanation_label.setText(
                "当前数据库没有遗留刷题记录，无需归档。原表仍会保留，直到迁移流程"
                "经过完整验证。"
            )
            self.export_button.setEnabled(False)
        self.target_thread.clear()
        for thread in self.repository.list_threads():
            self.target_thread.addItem(thread.title, thread.id)
        records = self.database.list_problems(newest_first=False)
        self.records_table.setRowCount(len(records))
        for row, record in enumerate(records):
            choice = QTableWidgetItem()
            choice.setFlags(
                choice.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            choice.setCheckState(Qt.CheckState.Unchecked)
            choice.setData(Qt.ItemDataRole.UserRole, record.id)
            self.records_table.setItem(row, 0, choice)
            for column, value in enumerate(
                (str(record.lc_number), record.title, record.date_solved), start=1
            ):
                self.records_table.setItem(row, column, QTableWidgetItem(value))
        self.migrate_button.setEnabled(
            bool(records)
            and self.target_thread.count() > 0
            and self.last_archive_path is not None
        )

    def _suggested_path(self) -> str:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        root = Path(documents) if documents else self.database.path.parent
        return str(root / "Nana-legacy-problems.json")

    def choose_and_export(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存 Nana 遗留数据归档",
            self._suggested_path(),
            "JSON 归档 (*.json)",
        )
        if not path:
            return
        self.export_to(Path(path))

    def export_to(self, path: str | Path) -> bool:
        archive_path = Path(path)
        try:
            archive = export_legacy_problems(self.database, archive_path)
        except FileExistsError:
            QMessageBox.warning(
                self,
                "未覆盖已有文件",
                "目标文件已经存在。请选择新的文件名，以免覆盖已有归档。",
            )
            return False
        except (LegacyArchiveError, OSError, ValueError) as error:
            QMessageBox.critical(self, "归档失败", str(error))
            return False

        self.last_archive_path = archive_path
        self.archive_status.setText(
            f"归档已校验：{archive.record_count} 条记录\n{archive_path}"
        )
        QMessageBox.information(
            self,
            "归档完成",
            f"已无损归档并校验 {archive.record_count} 条记录。\n"
            "原数据库没有被修改。",
        )
        self.refresh()
        return True

    def migrate_selected(self) -> None:
        record_ids: list[int] = []
        for row in range(self.records_table.rowCount()):
            item = self.records_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                record_ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        thread_id = self.target_thread.currentData()
        if thread_id is None:
            QMessageBox.information(self, "缺少研究线程", "请先创建一个研究线程。")
            return
        if self.last_archive_path is None:
            QMessageBox.information(
                self, "请先归档", "选择性迁移前必须先完成并校验无损归档。"
            )
            return
        try:
            migrated = migrate_legacy_records(
                self.database, self.repository, str(thread_id), record_ids
            )
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "迁移失败", str(error))
            return
        QMessageBox.information(
            self,
            "迁移完成",
            f"已将 {len(migrated)} 条记录迁移为 case Source。\n"
            "遗留数据库仍保持原样。",
        )
        self.refresh()
