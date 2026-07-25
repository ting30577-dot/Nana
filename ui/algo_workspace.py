"""Algorithm workspace for the v0.1 sliding-window module."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from visualizer.array_canvas import ArrayCanvas


EXAMPLE_CODE = """def max_sum_fixed_window(nums, k):
    window_sum = sum(nums[:k])
    best = window_sum

    for right in range(k, len(nums)):
        left = right - k
        window_sum += nums[right] - nums[left]
        best = max(best, window_sum)

    return best
"""


class InfoCard(QFrame):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self.setObjectName("panel")
        title = QLabel(label)
        title.setStyleSheet("color: #8b949e; font-size: 11px;")
        content = QLabel(value)
        content.setWordWrap(True)
        content.setStyleSheet("font-weight: 600;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(title)
        layout.addWidget(content)


class AlgorithmWorkspace(QWidget):
    def __init__(self) -> None:
        super().__init__()

        pattern_tree = QTreeWidget()
        pattern_tree.setHeaderLabel("算法模式")
        pattern_tree.setFixedWidth(230)
        root = QTreeWidgetItem(pattern_tree, ["滑动窗口"])
        QTreeWidgetItem(root, ["固定窗口"])
        QTreeWidgetItem(root, ["可变窗口 · 即将推出"])
        root.setExpanded(True)
        pattern_tree.setCurrentItem(root.child(0))

        heading = QLabel("固定滑动窗口")
        heading.setObjectName("pageTitle")
        subtitle = QLabel("维护长度为 k 的连续区间，用增量更新代替重复计算。")
        subtitle.setObjectName("mutedText")

        cards = QGridLayout()
        cards.setSpacing(10)
        cards.addWidget(InfoCard("适用场景", "固定长度连续子数组"), 0, 0)
        cards.addWidget(InfoCard("时间复杂度", "O(n)"), 0, 1)
        cards.addWidget(InfoCard("空间复杂度", "O(1)"), 0, 2)
        cards.addWidget(InfoCard("核心约束", "right - left + 1 = k"), 0, 3)

        code_editor = QPlainTextEdit(EXAMPLE_CODE)
        code_editor.setReadOnly(True)
        code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.canvas = ArrayCanvas()
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(code_editor)
        split.addWidget(self.canvas)
        split.setSizes([430, 570])

        start = QPushButton("开始")
        pause = QPushButton("暂停")
        reset = QPushButton("重置")
        step = QPushButton("单步")
        speed = QSlider(Qt.Orientation.Horizontal)
        speed.setRange(1, 10)
        speed.setValue(5)
        speed.setFixedWidth(140)

        start.clicked.connect(self.canvas.start)
        pause.clicked.connect(self.canvas.pause)
        reset.clicked.connect(self.canvas.reset)
        step.clicked.connect(self.canvas.step_once)
        speed.valueChanged.connect(self.canvas.set_speed)

        controls = QHBoxLayout()
        controls.addWidget(start)
        controls.addWidget(pause)
        controls.addWidget(reset)
        controls.addWidget(step)
        controls.addStretch()
        controls.addWidget(QLabel("速度"))
        controls.addWidget(speed)

        related = QLabel("关联题目：LeetCode 643 · Maximum Average Subarray I")
        related.setStyleSheet("color: #58a6ff;")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(14)
        main_layout.addWidget(heading)
        main_layout.addWidget(subtitle)
        main_layout.addLayout(cards)
        main_layout.addWidget(split, 1)
        main_layout.addLayout(controls)
        main_layout.addWidget(related)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(pattern_tree)
        root_layout.addLayout(main_layout, 1)

