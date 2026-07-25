"""算法工作台页面。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from visualizer.array_canvas import ArrayCanvas


@dataclass(frozen=True, slots=True)
class PatternInfo:
    title: str
    subtitle: str
    time: str
    space: str
    scene: str
    constraint: str
    code: str
    links: tuple[tuple[str, str], ...]


FIXED_INFO = PatternInfo(
    title="固定窗口",
    subtitle="窗口长度固定，每次右移一格并增量更新窗口统计量。",
    time="O(n)",
    space="O(k)",
    scene="定长子数组",
    constraint="right - left + 1 = k",
    code="""def max_sum_subarray(nums, k):
    # 初始化第一个窗口
    window_sum = sum(nums[:k])
    max_sum = window_sum

    # 滑动窗口：移入新元素，移出旧元素
    for i in range(k, len(nums)):
        window_sum += nums[i] - nums[i - k]
        max_sum = max(max_sum, window_sum)

    return max_sum""",
    links=(
        ("#643", "https://leetcode.com/problems/maximum-average-subarray-i/"),
        (
            "#1343",
            "https://leetcode.com/problems/number-of-sub-arrays-of-size-k-and-average-greater-than-or-equal-to-threshold/",
        ),
        ("#2090", "https://leetcode.com/problems/k-radius-subarray-averages/"),
    ),
)

VARIABLE_INFO = PatternInfo(
    title="可变窗口",
    subtitle="右指针扩张，满足条件后左指针收缩，寻找最优区间。",
    time="O(n)",
    space="O(1)",
    scene="满足条件的最短/长子数组",
    constraint="window_sum >= target",
    code="""def min_subarray_len(target, nums):
    l = 0
    window_sum = 0
    min_len = float('inf')

    for r in range(len(nums)):
        window_sum += nums[r]  # r 扩张

        # 满足条件时，收缩左边界
        while window_sum >= target:
            min_len = min(min_len, r - l + 1)
            window_sum -= nums[l]
            l += 1

    return min_len if min_len != float('inf') else 0""",
    links=(
        ("#3", "https://leetcode.com/problems/longest-substring-without-repeating-characters/"),
        ("#76", "https://leetcode.com/problems/minimum-window-substring/"),
        ("#209", "https://leetcode.com/problems/minimum-size-subarray-sum/"),
        ("#239", "https://leetcode.com/problems/sliding-window-maximum/"),
    ),
)


class InfoCard(QFrame):
    """算法信息卡。"""

    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self.setObjectName("infoCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        label_widget = QLabel(label)
        label_widget.setObjectName("cardLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("cardValue")
        value_widget.setWordWrap(True)
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)


class AlgorithmWorkspace(QWidget):
    """包含模式树、代码展示和 Matplotlib 动画的完整工作台。"""

    def __init__(self) -> None:
        super().__init__()
        self._pattern = FIXED_INFO

        self.pattern_tree = QTreeWidget()
        self.pattern_tree.setHeaderLabel("算法模式")
        self.pattern_tree.setFixedWidth(214)
        self.pattern_tree.setRootIsDecorated(True)
        root = QTreeWidgetItem(self.pattern_tree, ["滑动窗口"])
        fixed_item = QTreeWidgetItem(root, ["固定窗口"])
        variable_item = QTreeWidgetItem(root, ["可变窗口"])
        fixed_item.setData(0, Qt.ItemDataRole.UserRole, "fixed")
        variable_item.setData(0, Qt.ItemDataRole.UserRole, "variable")
        root.setExpanded(True)
        self.pattern_tree.setCurrentItem(fixed_item)
        self.pattern_tree.itemClicked.connect(self._pattern_clicked)

        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("mutedText")
        self.subtitle_label.setWordWrap(True)

        self.cards_layout = QGridLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)

        self.code_view = QTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.code_view.setFont(QFont("Consolas", 10))
        self.code_view.setMinimumWidth(340)

        self.canvas = ArrayCanvas()

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(130)
        self.speed_slider.valueChanged.connect(self.canvas.set_speed)

        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.reset_button = QPushButton("重置")
        self.step_button = QPushButton("单步")
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.pause_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        )
        self.reset_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.step_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward)
        )
        self.start_button.clicked.connect(self.canvas.start)
        self.pause_button.clicked.connect(self.canvas.pause)
        self.reset_button.clicked.connect(self.canvas.reset)
        self.step_button.clicked.connect(self.canvas.step_once)

        self.links_label = QLabel()
        self.links_label.setOpenExternalLinks(False)
        self.links_label.linkActivated.connect(self._open_link)
        self.links_label.setTextFormat(Qt.TextFormat.RichText)
        self.links_label.setStyleSheet("color: #818cf8;")

        self._build_layout()
        self._apply_pattern(FIXED_INFO)

    def _build_layout(self) -> None:
        pattern_panel = QWidget()
        pattern_panel.setFixedWidth(240)
        pattern_panel.setStyleSheet("background: #14172a;")
        pattern_panel_layout = QVBoxLayout(pattern_panel)
        pattern_panel_layout.setContentsMargins(16, 20, 10, 16)
        pattern_panel_layout.addWidget(self.pattern_tree)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(26, 22, 26, 18)
        right_layout.setSpacing(12)

        right_layout.addWidget(self.title_label)
        right_layout.addWidget(self.subtitle_label)
        right_layout.addLayout(self.cards_layout)

        split = QHBoxLayout()
        split.setSpacing(12)
        split.addWidget(self.code_view, 1)
        split.addWidget(self.canvas, 1)
        right_layout.addLayout(split, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("速度"))
        controls.addWidget(QLabel("慢"))
        controls.addWidget(self.speed_slider)
        controls.addWidget(QLabel("快"))
        controls.addSpacing(8)
        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.step_button)
        controls.addStretch(1)
        right_layout.addLayout(controls)
        right_layout.addWidget(self.links_label)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(pattern_panel)
        outer.addWidget(right_panel, 1)

    def _pattern_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        mode = item.data(0, Qt.ItemDataRole.UserRole)
        if mode == "fixed":
            self._apply_pattern(FIXED_INFO)
        elif mode == "variable":
            self._apply_pattern(VARIABLE_INFO)

    def _apply_pattern(self, pattern: PatternInfo) -> None:
        self._pattern = pattern
        self.title_label.setText(f"滑动窗口 · {pattern.title}")
        self.subtitle_label.setText(pattern.subtitle)

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        cards = (
            ("时间复杂度", pattern.time),
            ("空间复杂度", pattern.space),
            ("适用场景", pattern.scene),
            ("核心约束", pattern.constraint),
        )
        for column, (label, value) in enumerate(cards):
            self.cards_layout.addWidget(InfoCard(label, value), 0, column)

        self.code_view.setHtml(self._highlight_code(pattern.code))
        self.canvas.set_mode("fixed" if pattern is FIXED_INFO else "variable")
        links = "　".join(
            f'<a href="{html.escape(url)}" style="color:#818cf8;">LeetCode {html.escape(label)}</a>'
            for label, url in pattern.links
        )
        self.links_label.setText(f"关联题目：{links}")

    @staticmethod
    def _highlight_code(code: str) -> str:
        """对展示代码做轻量手动着色，不引入额外语法高亮依赖。"""

        keywords = (
            "def|return|for|in|range|while|if|else|float|inf|max|min|sum"
        )
        lines = html.escape(code, quote=False).splitlines()
        rendered = []
        for line in lines:
            if "#" in line:
                code_part, comment = line.split("#", 1)
                code_part = re.sub(
                    rf"\b({keywords})\b",
                    r'<span style="color:#c084fc;">\1</span>',
                    code_part,
                )
                line = f'{code_part}<span style="color:#6b7280;">#{comment}</span>'
            else:
                line = re.sub(
                    rf"\b({keywords})\b",
                    r'<span style="color:#c084fc;">\1</span>',
                    line,
                )
            rendered.append(line)
        return (
            '<pre style="font-family: Consolas, monospace; font-size: 11pt; '
            'color:#d1d5db; line-height: 1.45;">'
            + "\n".join(rendered)
            + "</pre>"
        )

    @staticmethod
    def _open_link(url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))
