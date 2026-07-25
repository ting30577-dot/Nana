"""Compact application navigation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    page_selected = Signal(int)

    ITEMS = (
        ("算", "算法工作台"),
        ("文", "论文库"),
        ("题", "刷题追踪"),
        ("图", "知识图谱"),
        ("设", "设置"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(60)
        self.setStyleSheet(
            """
            Sidebar {
                background: #0d1117;
                border-right: 1px solid #30363d;
            }
            QPushButton {
                min-width: 42px;
                min-height: 42px;
                padding: 0;
                border: 0;
                border-radius: 8px;
                color: #8b949e;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton:hover {
                color: #f0f6fc;
                background: #21262d;
            }
            QPushButton:checked {
                color: #58a6ff;
                background: #1f2937;
                border-left: 3px solid #58a6ff;
            }
            """
        )

        group = QButtonGroup(self)
        group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 16, 9, 16)
        layout.setSpacing(10)

        for index, (label, tooltip) in enumerate(self.ITEMS):
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, page=index: self.page_selected.emit(page)
            )
            group.addButton(button, index)
            layout.addWidget(button)
            if index == 3:
                layout.addStretch()

        group.button(0).setChecked(True)

