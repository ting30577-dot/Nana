"""v0.2.0-dev 遗留刷题记录页；数据导出/迁移后将在 alpha 前退役。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from db.database import Database
from ui.theme import DIALOG_STYLESHEET, PALETTE

matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False

PATTERN_NAMES = ("滑动窗口", "双指针", "前缀和", "二分查找", "单调栈", "其他")


@dataclass(frozen=True, slots=True)
class ProblemFormData:
    lc_number: int
    title: str
    difficulty: str
    pattern: str
    date_solved: str
    status: str
    notes: str


class ProblemDialog(QDialog):
    """新增算法练习记录对话框。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新增算法练习")
        self.setMinimumWidth(440)
        self.setStyleSheet(DIALOG_STYLESHEET)

        self.number_input = QSpinBox()
        self.number_input.setRange(1, 100000)
        self.number_input.setValue(1)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：两数之和 II")

        self.difficulty_input = QComboBox()
        self.difficulty_input.addItems(Database.DIFFICULTIES)

        self.pattern_input = QComboBox()
        self.pattern_input.addItems(PATTERN_NAMES)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")

        self.status_input = QComboBox()
        self.status_input.addItems(Database.STATUSES)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("记录关键思路、易错点或复习提醒")
        self.notes_input.setMaximumHeight(110)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("题号", self.number_input)
        form.addRow("题名", self.title_input)
        form.addRow("难度", self.difficulty_input)
        form.addRow("所属模式", self.pattern_input)
        form.addRow("完成日期", self.date_input)
        form.addRow("状态", self.status_input)
        form.addRow("笔记", self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "无法保存", "请填写题名。")
            self.title_input.setFocus()
            return
        self.accept()

    def data(self) -> ProblemFormData:
        return ProblemFormData(
            lc_number=self.number_input.value(),
            title=self.title_input.text().strip(),
            difficulty=self.difficulty_input.currentText(),
            pattern=self.pattern_input.currentText(),
            date_solved=self.date_input.date().toString("yyyy-MM-dd"),
            status=self.status_input.currentText(),
            notes=self.notes_input.toPlainText().strip(),
        )


class StatCard(QFrame):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.setObjectName("infoCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        label_widget = QLabel(label)
        label_widget.setObjectName("cardLabel")
        self.value_widget = QLabel("0")
        self.value_widget.setObjectName("statValue")
        layout.addWidget(label_widget)
        layout.addWidget(self.value_widget)

    def set_value(self, value: int) -> None:
        self.value_widget.setText(str(value))


class PatternChart(FigureCanvas):
    def __init__(self) -> None:
        self.figure = Figure(figsize=(4.5, 3), facecolor=PALETTE["surface"])
        super().__init__(self.figure)
        self.setMinimumHeight(235)
        self.setMaximumHeight(310)
        self.update_counts({})

    def update_counts(self, counts: dict[str, int]) -> None:
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(PALETTE["surface"])
        if not counts:
            axes.text(
                0.5,
                0.54,
                "还没有算法练习记录",
                transform=axes.transAxes,
                ha="center",
                va="center",
                color=PALETTE["text_soft"],
                fontsize=12,
            )
            axes.text(
                0.5,
                0.42,
                "新增记录后，这里会显示模式分布",
                transform=axes.transAxes,
                ha="center",
                va="center",
                color=PALETTE["subtle"],
                fontsize=9,
            )
            axes.set_axis_off()
        else:
            labels = list(counts)
            values = [counts[label] for label in labels]
            positions = list(range(len(labels)))
            axes.barh(positions, values, color=PALETTE["primary"], height=0.55)
            axes.set_yticks(positions, labels)
            axes.invert_yaxis()
            axes.tick_params(axis="y", colors=PALETTE["text_soft"], labelsize=9)
            axes.tick_params(axis="x", colors=PALETTE["subtle"], labelsize=8)
            axes.xaxis.grid(True, color=PALETTE["border"], linewidth=0.8)
            axes.set_axisbelow(True)
            axes.set_title(
                "按算法模式统计",
                color=PALETTE["text"],
                fontsize=11,
                pad=10,
            )
            for position, value in zip(positions, values):
                axes.text(
                    value + max(values) * 0.025,
                    position,
                    str(value),
                    va="center",
                    color=PALETTE["text"],
                    fontsize=9,
                )
            axes.set_xlim(0, max(values) * 1.18 + 0.2)
            for spine in axes.spines.values():
                spine.set_visible(False)
        self.figure.tight_layout(pad=1.3)
        self.draw_idle()


class TrackerPage(QWidget):
    """可新增、删除、筛选并持久化的算法练习页。"""

    def __init__(
        self,
        database: Database | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database or Database()

        title = QLabel("算法练习")
        title.setObjectName("pageTitle")
        subtitle = QLabel("记录算法模式、边界和复盘，让练习服务于方法理解。")
        subtitle.setObjectName("mutedText")

        self.total_card = StatCard("总题数")
        self.easy_card = StatCard("Easy")
        self.medium_card = StatCard("Medium")
        self.hard_card = StatCard("Hard")

        stats = QHBoxLayout()
        stats.setSpacing(10)
        stats.addWidget(self.total_card)
        stats.addWidget(self.easy_card)
        stats.addWidget(self.medium_card)
        stats.addWidget(self.hard_card)

        self.pattern_filter = QComboBox()
        self.pattern_filter.addItem("全部模式", None)
        for pattern in PATTERN_NAMES:
            self.pattern_filter.addItem(pattern, pattern)
        self.pattern_filter.currentIndexChanged.connect(self.refresh)

        self.difficulty_filter = QComboBox()
        self.difficulty_filter.addItem("全部难度", None)
        for difficulty in Database.DIFFICULTIES:
            self.difficulty_filter.addItem(difficulty, difficulty)
        self.difficulty_filter.currentIndexChanged.connect(self.refresh)

        self.sort_order = QComboBox()
        self.sort_order.addItem("日期：从新到旧", True)
        self.sort_order.addItem("日期：从旧到新", False)
        self.sort_order.currentIndexChanged.connect(self.refresh)

        self.add_button = QPushButton("新增练习")
        self.add_button.clicked.connect(self.add_problem)
        self.delete_button = QPushButton("删除记录")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_selected)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self.pattern_filter)
        filters.addWidget(self.difficulty_filter)
        filters.addWidget(self.sort_order)
        filters.addStretch(1)
        filters.addWidget(self.add_button)
        filters.addWidget(self.delete_button)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ("题号", "题名", "难度", "模式", "日期", "状态", "笔记")
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self.chart = PatternChart()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(stats)
        layout.addWidget(self.chart)
        layout.addLayout(filters)
        layout.addWidget(self.table, 1)

        self.refresh()

    def add_problem(self) -> None:
        dialog = ProblemDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        try:
            self.database.add_problem(
                lc_number=data.lc_number,
                title=data.title,
                difficulty=data.difficulty,
                pattern=data.pattern,
                date_solved=data.date_solved,
                status=data.status,
                notes=data.notes,
            )
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "题目已存在",
                f"LeetCode #{data.lc_number} 已经在算法练习中。",
            )
            return
        except ValueError as error:
            QMessageBox.warning(self, "无法保存", str(error))
            return
        self.refresh()

    def delete_selected(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "请选择记录", "请先选择要删除的一行。")
            return

        row = selected_rows[0].row()
        first_item = self.table.item(row, 0)
        record_id = first_item.data(Qt.ItemDataRole.UserRole)
        title = self.table.item(row, 1).text()
        answer = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除“{title}”吗？此操作无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.database.delete_problem(int(record_id))
        self.refresh()

    def refresh(self, *_args: object) -> None:
        records = self.database.list_problems(
            pattern=self.pattern_filter.currentData(),
            difficulty=self.difficulty_filter.currentData(),
            newest_first=bool(self.sort_order.currentData()),
        )
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                str(record.lc_number),
                record.title,
                record.difficulty,
                record.pattern,
                record.date_solved,
                record.status,
                record.notes,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record.id)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)

        difficulty = self.database.difficulty_counts()
        self.total_card.set_value(self.database.total_count())
        self.easy_card.set_value(difficulty["Easy"])
        self.medium_card.set_value(difficulty["Medium"])
        self.hard_card.set_value(difficulty["Hard"])
        self.chart.update_counts(self.database.pattern_counts())
