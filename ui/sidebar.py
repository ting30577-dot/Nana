"""AlgoMind 左侧导航栏。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    """60px 宽的垂直导航栏。

    v0.1 只开放算法工作台，其余入口保留位置并提示 Coming soon。
    """

    navigation_requested = Signal(int, str)

    ITEMS = (
        ("算", "算法"),
        ("文", "论文"),
        ("题", "刷题"),
        ("图", "图谱"),
        ("设", "设置"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(60)
        self.setStyleSheet(
            """
            Sidebar {
                background: #1a1d27;
            }
            QPushButton {
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
                padding: 0;
                border: 0;
                border-radius: 8px;
                color: #9ca3af;
                background: transparent;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton:hover {
                color: #f9fafb;
                background: #292d3d;
            }
            QPushButton:checked {
                color: #f9fafb;
                background: #6366f1;
            }
            """
        )

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 16, 9, 16)
        layout.setSpacing(10)

        for index, (symbol, name) in enumerate(self.ITEMS):
            button = QPushButton(symbol)
            button.setToolTip(name)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, item_index=index, item_name=name: (
                    self.navigation_requested.emit(item_index, item_name)
                )
            )
            self._group.addButton(button, index)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
            if index == 3:
                layout.addStretch(1)

        self._group.button(0).setChecked(True)

    def keep_algorithm_selected(self) -> None:
        """非算法入口点击后恢复算法入口的激活状态。"""

        self._group.button(0).setChecked(True)
