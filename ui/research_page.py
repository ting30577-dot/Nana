"""v0.2.0-alpha 的 Research Thread 最小工作台。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from nana_core.research import ResearchRepository, ResearchThread
from nana_core.research.models import Claim, Evidence, Experiment, Insight, Method, Source
from ui.research_asset_dialog import FieldSpec, ResearchAssetDialog
from ui.theme import DIALOG_STYLESHEET


@dataclass(frozen=True, slots=True)
class ResearchThreadFormData:
    title: str
    question: str
    scope_exclusions: str
    completion_criteria: str
    next_step: str


class ResearchThreadDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建研究线程")
        self.setMinimumWidth(520)
        self.setStyleSheet(DIALOG_STYLESHEET)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：验证有序数组双指针的不变量")
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("我真正想弄清什么？")
        self.question_input.setMaximumHeight(90)
        self.scope_input = QTextEdit()
        self.scope_input.setPlaceholderText("本线程明确不处理什么？")
        self.scope_input.setMaximumHeight(70)
        self.criteria_input = QTextEdit()
        self.criteria_input.setPlaceholderText("什么证据出现时，这个问题才算完成？")
        self.criteria_input.setMaximumHeight(70)
        self.next_step_input = QLineEdit()
        self.next_step_input.setPlaceholderText("第一个可执行动作")

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("标题", self.title_input)
        form.addRow("研究问题", self.question_input)
        form.addRow("范围外", self.scope_input)
        form.addRow("完成标准", self.criteria_input)
        form.addRow("下一步", self.next_step_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("创建线程")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "无法创建", "请填写线程标题。")
            self.title_input.setFocus()
            return
        if not self.question_input.toPlainText().strip():
            QMessageBox.warning(self, "无法创建", "请填写明确的研究问题。")
            self.question_input.setFocus()
            return
        self.accept()

    def data(self) -> ResearchThreadFormData:
        return ResearchThreadFormData(
            title=self.title_input.text().strip(),
            question=self.question_input.toPlainText().strip(),
            scope_exclusions=self.scope_input.toPlainText().strip(),
            completion_criteria=self.criteria_input.toPlainText().strip(),
            next_step=self.next_step_input.text().strip(),
        )


class ResearchPage(QWidget):
    """创建、浏览并重新打开 Research Thread 的最小界面。"""

    def __init__(
        self,
        repository: ResearchRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository

        title = QLabel("研究线程")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "从一个真实问题开始，把来源、方法、证据、实验和判断留在同一条线上。"
        )
        subtitle.setObjectName("mutedText")
        self.add_button = QPushButton("新建研究线程")
        self.add_button.clicked.connect(self.add_thread)

        heading = QHBoxLayout()
        heading.addWidget(title)
        heading.addStretch(1)
        heading.addWidget(self.add_button)

        self.thread_list = QListWidget()
        self.thread_list.setMinimumWidth(280)
        self.thread_list.setMaximumWidth(380)
        self.thread_list.currentItemChanged.connect(self._show_selected)

        self.detail_card = QFrame()
        self.detail_card.setObjectName("infoCard")
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(22, 20, 22, 20)
        detail_layout.setSpacing(12)

        self.detail_title = QLabel("还没有研究线程")
        self.detail_title.setObjectName("pageTitle")
        self.detail_question = self._detail_label("先创建一个明确问题。")
        self.detail_scope = self._detail_label("")
        self.detail_criteria = self._detail_label("")
        self.detail_next_step = self._detail_label("")
        self.detail_status = QLabel("")
        self.complete_button = QPushButton("标记线程完成")
        self.complete_button.setEnabled(False)
        self.complete_button.clicked.connect(self.complete_current_thread)
        self.detail_status.setObjectName("mutedText")

        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_status)
        detail_layout.addWidget(self.complete_button, 0, Qt.AlignmentFlag.AlignLeft)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(QLabel("研究问题"))
        detail_layout.addWidget(self.detail_question)
        detail_layout.addWidget(QLabel("范围外"))
        detail_layout.addWidget(self.detail_scope)
        detail_layout.addWidget(QLabel("完成标准"))
        detail_layout.addWidget(self.detail_criteria)
        detail_layout.addWidget(QLabel("下一步"))
        detail_layout.addWidget(self.detail_next_step)
        detail_layout.addSpacing(8)
        asset_heading = QHBoxLayout()
        asset_heading.addWidget(QLabel("研究资产"))
        asset_heading.addStretch(1)
        self.asset_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("source", "来源"),
            ("claim", "主张"),
            ("evidence", "证据"),
            ("method", "方法"),
            ("experiment", "实验"),
            ("insight", "判断"),
        ):
            button = QPushButton(f"+ {label}")
            button.setEnabled(False)
            button.clicked.connect(
                lambda _checked=False, asset_key=key: self.add_asset(asset_key)
            )
            self.asset_buttons[key] = button
            asset_heading.addWidget(button)
        detail_layout.addLayout(asset_heading)
        self.asset_list = QListWidget()
        self.asset_list.setMinimumHeight(180)
        detail_layout.addWidget(self.asset_list, 1)
        detail_layout.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.thread_list)
        body.addWidget(self.detail_card, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(12)
        layout.addLayout(heading)
        layout.addWidget(subtitle)
        layout.addLayout(body, 1)
        self._current_thread_id: str | None = None
        self.refresh()

    @staticmethod
    def _detail_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def add_thread(self) -> None:
        dialog = ResearchThreadDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.create_thread(dialog.data())
        except ValueError as error:
            QMessageBox.warning(self, "无法创建", str(error))

    def create_thread(self, data: ResearchThreadFormData) -> ResearchThread:
        thread = self.repository.create_thread(
            title=data.title,
            question=data.question,
            scope_exclusions=data.scope_exclusions,
            completion_criteria=data.completion_criteria,
            status="active",
            next_step=data.next_step,
        )
        self.refresh(select_id=thread.id)
        return thread

    def refresh(self, *, select_id: str | None = None) -> None:
        current = select_id
        if current is None and self.thread_list.currentItem() is not None:
            current = self.thread_list.currentItem().data(Qt.ItemDataRole.UserRole)

        self.thread_list.clear()
        selected_item: QListWidgetItem | None = None
        for thread in self.repository.list_threads():
            item = QListWidgetItem(thread.title)
            item.setToolTip(thread.question)
            item.setData(Qt.ItemDataRole.UserRole, thread.id)
            self.thread_list.addItem(item)
            if thread.id == current:
                selected_item = item

        if selected_item is not None:
            self.thread_list.setCurrentItem(selected_item)
        elif self.thread_list.count():
            self.thread_list.setCurrentRow(0)
        else:
            self._show_thread(None)

    def _show_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        thread_id = (
            current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        )
        self._show_thread(
            self.repository.get_thread(thread_id) if thread_id is not None else None
        )

    def _show_thread(self, thread: ResearchThread | None) -> None:
        self._current_thread_id = thread.id if thread is not None else None
        for button in self.asset_buttons.values():
            button.setEnabled(thread is not None)
        self.complete_button.setEnabled(
            thread is not None and thread.status != "completed"
        )
        if thread is None:
            self.detail_title.setText("还没有研究线程")
            self.detail_status.setText("")
            self.detail_question.setText("先创建一个明确问题。")
            self.detail_scope.setText("—")
            self.detail_criteria.setText("—")
            self.detail_next_step.setText("—")
            self.asset_list.clear()
            return
        self.detail_title.setText(thread.title)
        self.detail_status.setText(f"状态：{thread.status}")
        self.detail_question.setText(thread.question)
        self.detail_scope.setText(thread.scope_exclusions or "—")
        self.detail_criteria.setText(thread.completion_criteria or "—")
        self.detail_next_step.setText(thread.next_step or "—")
        self._refresh_assets(thread.id)

    def complete_current_thread(self) -> None:
        if self._current_thread_id is None:
            return
        answer = QMessageBox.question(
            self,
            "确认完成",
            "确认当前问题已经形成方法、实验和个人判断？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        updated = self.repository.update_thread_status(
            self._current_thread_id,
            "completed",
            next_step="",
        )
        self.refresh(select_id=updated.id)

    def _refresh_assets(self, thread_id: str) -> None:
        self.asset_list.clear()
        groups = (
            ("来源", Source, lambda item: item.title),
            ("主张", Claim, lambda item: item.statement),
            ("证据", Evidence, lambda item: f"{item.locator} · {item.content}"),
            ("方法", Method, lambda item: item.name),
            ("实验", Experiment, lambda item: item.title),
            ("判断", Insight, lambda item: item.statement),
        )
        for label, model, describe in groups:
            for asset in self.repository.list_for_thread(model, thread_id):
                self.asset_list.addItem(f"{label}｜{describe(asset)}")

    @staticmethod
    def _relation_choices(items: list, label) -> tuple[tuple[str, str], ...]:
        return tuple((label(item), item.id) for item in items)

    def add_asset(self, kind: str) -> None:
        thread_id = self._current_thread_id
        if thread_id is None:
            return
        sources = self.repository.list_for_thread(Source, thread_id)
        claims = self.repository.list_for_thread(Claim, thread_id)
        methods = self.repository.list_for_thread(Method, thread_id)
        specifications = {
            "source": (
                "添加来源",
                (
                    FieldSpec(
                        "source_type",
                        "类型",
                        choices=tuple(
                            (label, value)
                            for label, value in (
                                ("论文", "paper"),
                                ("项目", "project"),
                                ("代码", "code"),
                                ("数据集", "dataset"),
                                ("博客", "blog"),
                                ("案例", "case"),
                            )
                        ),
                    ),
                    FieldSpec("title", "标题", True),
                    FieldSpec("locator", "链接或位置", True),
                    FieldSpec("version", "版本"),
                    FieldSpec("selection_reason", "选择理由", multiline=True),
                ),
            ),
            "claim": (
                "添加来源主张",
                (
                    FieldSpec(
                        "source_id",
                        "来源",
                        True,
                        self._relation_choices(sources, lambda item: item.title),
                    ),
                    FieldSpec("statement", "主张", True, multiline=True),
                ),
            ),
            "evidence": (
                "添加证据",
                (
                    FieldSpec(
                        "claim_id",
                        "主张",
                        True,
                        self._relation_choices(claims, lambda item: item.statement),
                    ),
                    FieldSpec("locator", "证据位置", True),
                    FieldSpec(
                        "evidence_type",
                        "类型",
                        choices=(
                            ("原文", "text"),
                            ("代码", "code"),
                            ("数据", "data"),
                            ("实验", "experiment"),
                        ),
                    ),
                    FieldSpec("content", "证据内容", True, multiline=True),
                    FieldSpec(
                        "verification_status",
                        "核对状态",
                        choices=(
                            ("待核对", "pending"),
                            ("已核对", "verified"),
                            ("不支持", "unsupported"),
                        ),
                    ),
                ),
            ),
            "method": (
                "添加方法",
                (
                    FieldSpec("name", "名称", True),
                    FieldSpec("problem", "解决的问题", True, multiline=True),
                    FieldSpec("mechanism", "关键机制", True, multiline=True),
                    FieldSpec("assumptions", "假设或不变量", multiline=True),
                    FieldSpec("applicability", "适用条件", multiline=True),
                    FieldSpec("failure_boundaries", "失败边界", multiline=True),
                ),
            ),
            "experiment": (
                "添加实验",
                (
                    FieldSpec(
                        "method_id",
                        "方法",
                        True,
                        self._relation_choices(methods, lambda item: item.name),
                    ),
                    FieldSpec("title", "标题", True),
                    FieldSpec("purpose", "目的", True, multiline=True),
                    FieldSpec("environment", "环境"),
                    FieldSpec("inputs", "输入与参数", multiline=True),
                    FieldSpec("result", "结果与日志", multiline=True),
                    FieldSpec("limitations", "限制或反例", multiline=True),
                ),
            ),
            "insight": (
                "添加个人判断",
                (
                    FieldSpec(
                        "method_id",
                        "方法",
                        True,
                        self._relation_choices(methods, lambda item: item.name),
                    ),
                    FieldSpec("statement", "判断", True, multiline=True),
                    FieldSpec(
                        "confidence",
                        "置信度",
                        choices=(("低", "low"), ("中", "medium"), ("高", "high")),
                    ),
                    FieldSpec("next_action", "下一步行动"),
                ),
            ),
        }
        if kind not in specifications:
            return
        title, fields = specifications[kind]
        if kind in {"claim", "evidence", "experiment", "insight"}:
            relation_available = {
                "claim": bool(sources),
                "evidence": bool(claims),
                "experiment": bool(methods),
                "insight": bool(methods),
            }[kind]
            if not relation_available:
                prerequisites = {
                    "claim": "请先添加来源。",
                    "evidence": "请先添加主张。",
                    "experiment": "请先添加方法。",
                    "insight": "请先添加方法。",
                }
                QMessageBox.information(self, "缺少关联对象", prerequisites[kind])
                return
        dialog = ResearchAssetDialog(title, fields, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            if kind == "source":
                self.repository.create_source(thread_id, **values)
            elif kind == "claim":
                source_id = values.pop("source_id")
                self.repository.create_claim(thread_id, source_id, **values)
            elif kind == "evidence":
                claim_id = values.pop("claim_id")
                claim = next(item for item in claims if item.id == claim_id)
                self.repository.create_evidence(
                    thread_id, claim.source_id, claim_id, **values
                )
            elif kind == "method":
                self.repository.create_method(thread_id, **values)
            elif kind == "experiment":
                method_id = values.pop("method_id")
                self.repository.create_experiment(thread_id, method_id, **values)
            elif kind == "insight":
                method_id = values.pop("method_id")
                self.repository.create_insight(thread_id, method_id, **values)
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "无法保存", str(error))
            return
        self._refresh_assets(thread_id)
