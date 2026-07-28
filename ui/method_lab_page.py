"""以研究线程中的 Method 与 Experiment 为中心的方法实验室骨架。"""

from __future__ import annotations

import json

from algorithms.two_pointers import collision_steps
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nana_core.research import Experiment, Method, ResearchRepository


class MethodLabPage(QWidget):
    def __init__(
        self,
        repository: ResearchRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self._current_thread_id: str | None = None
        self._current_method: Method | None = None

        title = QLabel("方法实验室")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "可视化和测试是研究证据视图；实验必须关联 Method 与 Research Thread。"
        )
        subtitle.setObjectName("mutedText")

        self.method_list = QListWidget()
        self.method_list.setMinimumWidth(290)
        self.method_list.currentItemChanged.connect(self._show_selected)

        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        self.method_title = QLabel("还没有方法")
        self.method_title.setObjectName("pageTitle")
        self.problem = QLabel("从研究线程中添加 Method。")
        self.problem.setWordWrap(True)
        self.mechanism = QLabel("—")
        self.mechanism.setWordWrap(True)
        self.boundaries = QLabel("—")
        self.boundaries.setWordWrap(True)
        self.experiments = QListWidget()
        runner = QFrame()
        runner.setObjectName("infoCard")
        runner_layout = QVBoxLayout(runner)
        runner_layout.setContentsMargins(14, 12, 14, 12)
        runner_title = QLabel("双指针碰撞验证器")
        runner_title.setObjectName("codeSectionLabel")
        runner_hint = QLabel(
            "输入非递减整数数组与目标和；正常结果或失败边界都会保存为 Experiment。"
        )
        runner_hint.setWordWrap(True)
        runner_hint.setObjectName("mutedText")
        self.array_input = QLineEdit("[1, 2, 4, 6, 10]")
        self.array_input.setPlaceholderText("JSON 数组，例如 [1, 2, 4, 6, 10]")
        self.target_input = QLineEdit("8")
        self.target_input.setPlaceholderText("目标和")
        self.run_button = QPushButton("运行并保存实验")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.run_collision_experiment)
        runner_inputs = QHBoxLayout()
        runner_inputs.addWidget(self.array_input, 1)
        runner_inputs.addWidget(self.target_input)
        runner_inputs.addWidget(self.run_button)
        self.run_result = QLabel("尚未运行。")
        self.run_result.setWordWrap(True)
        self.run_result.setObjectName("mutedText")
        runner_layout.addWidget(runner_title)
        runner_layout.addWidget(runner_hint)
        runner_layout.addLayout(runner_inputs)
        runner_layout.addWidget(self.run_result)

        card_layout.addWidget(self.method_title)
        card_layout.addWidget(QLabel("解决的问题"))
        card_layout.addWidget(self.problem)
        card_layout.addWidget(QLabel("关键机制"))
        card_layout.addWidget(self.mechanism)
        card_layout.addWidget(QLabel("失败边界"))
        card_layout.addWidget(self.boundaries)
        card_layout.addWidget(QLabel("关联实验"))
        card_layout.addWidget(self.experiments, 1)
        card_layout.addWidget(runner)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.method_list)
        body.addWidget(card, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(body, 1)
        self.refresh()

    def refresh(self) -> None:
        current_id = None
        if self.method_list.currentItem() is not None:
            current_id = self.method_list.currentItem().data(
                Qt.ItemDataRole.UserRole
            )[1]
        self.method_list.clear()
        selected: QListWidgetItem | None = None
        for thread in self.repository.list_threads():
            for method in self.repository.list_for_thread(Method, thread.id):
                item = QListWidgetItem(f"{method.name}\n{thread.title}")
                item.setData(Qt.ItemDataRole.UserRole, (thread.id, method.id))
                item.setData(Qt.ItemDataRole.UserRole + 1, method)
                self.method_list.addItem(item)
                if method.id == current_id:
                    selected = item
        if selected is not None:
            self.method_list.setCurrentItem(selected)
        elif self.method_list.count():
            self.method_list.setCurrentRow(0)
        else:
            self._show_method(None, None)

    def _show_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._show_method(None, None)
            return
        thread_id, _method_id = current.data(Qt.ItemDataRole.UserRole)
        method = current.data(Qt.ItemDataRole.UserRole + 1)
        self._show_method(str(thread_id), method)

    def _show_method(self, thread_id: str | None, method: Method | None) -> None:
        self._current_thread_id = thread_id
        self._current_method = method
        self.run_button.setEnabled(method is not None and thread_id is not None)
        self.experiments.clear()
        if method is None or thread_id is None:
            self.method_title.setText("还没有方法")
            self.problem.setText("从研究线程中添加 Method。")
            self.mechanism.setText("—")
            self.boundaries.setText("—")
            return
        self.method_title.setText(method.name)
        self.problem.setText(method.problem)
        self.mechanism.setText(method.mechanism)
        self.boundaries.setText(method.failure_boundaries or "—")
        experiments = self.repository.list_for_thread(Experiment, thread_id)
        for experiment in experiments:
            if experiment.method_id == method.id:
                result = experiment.result or "尚未记录结果"
                self.experiments.addItem(f"{experiment.title}｜{result}")

    def run_collision_experiment(self) -> None:
        if self._current_thread_id is None or self._current_method is None:
            return
        try:
            values = json.loads(self.array_input.text())
            if (
                not isinstance(values, list)
                or any(isinstance(value, bool) or not isinstance(value, int) for value in values)
            ):
                raise ValueError("数组必须是 JSON 整数数组。")
            target = int(self.target_input.text())
        except (json.JSONDecodeError, ValueError) as error:
            QMessageBox.warning(self, "输入无效", str(error))
            return

        serialized_inputs = json.dumps(
            {"values": values, "target": target},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        limitations = ""
        try:
            states = collision_steps(values, target)
            final = states[-1].payload
            if final["total"] is not None:
                left = final["left"]
                right = final["right"]
                result = (
                    f"命中：index {left} + index {right}，"
                    f"{values[left]} + {values[right]} = {target}。"
                )
            else:
                result = f"未找到和为 {target} 的元素对。"
        except ValueError as error:
            result = f"输入被边界检查拒绝：{error}"
            limitations = str(error)

        experiment = self.repository.create_experiment(
            self._current_thread_id,
            self._current_method.id,
            title="双指针碰撞验证",
            purpose="验证单调排除过程或记录其失败边界。",
            environment="Nana 内置 collision_steps",
            inputs=serialized_inputs,
            result=result,
            limitations=limitations,
        )
        self.run_result.setText(result)
        self.experiments.addItem(f"{experiment.title}｜{experiment.result}")
