"""Array visualization widget for the fixed-window demo."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from algorithms.sliding_window import WindowState, fixed_window_steps


class ArrayCanvas(QWidget):
    VALUES = (2, 1, 5, 1, 3, 2, 4, 6)
    WINDOW_SIZE = 3

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(480, 300)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.step_once)
        self._steps: Iterator[WindowState]
        self._state: WindowState | None
        self.reset()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def pause(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self.pause()
        self._steps = iter(fixed_window_steps(self.VALUES, self.WINDOW_SIZE))
        self._state = None
        self.update()

    def set_speed(self, value: int) -> None:
        self._timer.setInterval(1300 - value * 100)

    def step_once(self) -> None:
        try:
            self._state = next(self._steps)
        except StopIteration:
            self.pause()
            return
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d1117"))

        margin = 36
        gap = 8
        available = self.width() - margin * 2
        cell_size = min(62, (available - gap * (len(self.VALUES) - 1)) // len(self.VALUES))
        total_width = cell_size * len(self.VALUES) + gap * (len(self.VALUES) - 1)
        start_x = (self.width() - total_width) // 2
        start_y = max(80, self.height() // 2 - cell_size)

        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        for index, value in enumerate(self.VALUES):
            x = start_x + index * (cell_size + gap)
            in_window = (
                self._state is not None
                and self._state.left <= index <= self._state.right
            )
            fill = QColor("#1f6feb" if in_window else "#21262d")
            border = QColor("#58a6ff" if in_window else "#30363d")
            painter.setBrush(fill)
            painter.setPen(QPen(border, 2))
            painter.drawRoundedRect(x, start_y, cell_size, cell_size, 8, 8)
            painter.setPen(QColor("#f0f6fc"))
            painter.drawText(
                x,
                start_y,
                cell_size,
                cell_size,
                Qt.AlignmentFlag.AlignCenter,
                str(value),
            )

        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor("#8b949e"))
        if self._state is None:
            message = "点击“开始”或“单步”观察窗口移动"
            summary = f"数组长度 {len(self.VALUES)} · 窗口大小 k = {self.WINDOW_SIZE}"
        else:
            message = self._state.message
            summary = (
                f"left = {self._state.left}   right = {self._state.right}"
                f"   当前和 = {self._state.window_sum}"
                f"   最大和 = {self._state.best_sum}"
            )
        painter.drawText(
            margin,
            start_y + cell_size + 38,
            self.width() - margin * 2,
            24,
            Qt.AlignmentFlag.AlignCenter,
            summary,
        )
        painter.setPen(QColor("#c9d1d9"))
        painter.drawText(
            margin,
            start_y + cell_size + 74,
            self.width() - margin * 2,
            48,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            message,
        )

