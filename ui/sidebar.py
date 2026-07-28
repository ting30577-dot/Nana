"""Nana 左侧导航栏。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

from ui.theme import SIDEBAR_STYLESHEET


class Sidebar(QWidget):
    """60px 宽的垂直导航栏。

    v0.2.0-alpha 建设期只暴露新研究入口与安全迁移入口。
    """

    navigation_requested = Signal(int, str)

    ITEMS = (
        ("研", "研究"),
        ("迁", "数据迁移"),
        ("法", "方法实验室"),
        ("设", "设置"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(60)
        self.setStyleSheet(SIDEBAR_STYLESHEET)

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
            if index == 2:
                layout.addStretch(1)

        self._group.button(0).setChecked(True)

    def select_item(self, index: int) -> None:
        """让指定侧边栏入口保持选中。"""

        button = self._group.button(index)
        if button is not None:
            button.setChecked(True)
