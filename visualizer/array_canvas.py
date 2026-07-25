"""使用 Matplotlib 绘制滑动窗口动画。"""

from __future__ import annotations

from typing import Literal

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer

from algorithms.sliding_window import (
    FixedWindowState,
    VariableWindowState,
)

AnimationMode = Literal["fixed", "variable"]

matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False


class ArrayCanvas(FigureCanvas):
    """嵌入 PySide6 的 Matplotlib 画布。

    动画由 QTimer 驱动，不使用 ``FuncAnimation``，方便暂停和单步控制。
    """

    FIXED_VALUES = (2, 1, 5, 1, 3, 2)
    FIXED_SIZE = 3
    VARIABLE_VALUES = (2, 3, 1, 2, 4, 3)
    VARIABLE_TARGET = 7

    def __init__(self) -> None:
        self.figure = Figure(figsize=(6, 4), facecolor="#0f1117")
        super().__init__(self.figure)
        self.setMinimumWidth(420)
        self.axes = self.figure.add_subplot(111)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.step_once)
        self._speed = 5
        self._mode: AnimationMode = "fixed"
        self._states: list[FixedWindowState | VariableWindowState] = []
        self._index = -1
        self.set_speed(self._speed)
        self.set_mode("fixed")

    def set_mode(self, mode: AnimationMode) -> None:
        """切换动画模式并回到初始画面。"""

        self._mode = mode
        if mode == "fixed":
            from algorithms.sliding_window import fixed_window_steps

            self._states = fixed_window_steps(self.FIXED_VALUES, self.FIXED_SIZE)
        else:
            from algorithms.sliding_window import variable_window_steps

            self._states = variable_window_steps(
                self.VARIABLE_VALUES,
                self.VARIABLE_TARGET,
            )
        self.reset()

    def set_speed(self, value: int) -> None:
        """将滑块值映射到 QTimer 间隔。"""

        self._speed = value
        self._timer.setInterval(max(100, 1100 - value * 100))

    def start(self) -> None:
        if self._index >= len(self._states) - 1:
            self._index = -1
        if self._index == -1:
            self.step_once()
        self._timer.start()

    def pause(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self.pause()
        self._index = -1
        self._draw_current()

    def step_once(self) -> None:
        if self._index >= len(self._states) - 1:
            self.pause()
            return
        self._index += 1
        self._draw_current()
        if self._index >= len(self._states) - 1:
            self.pause()

    def _draw_current(self) -> None:
        self.axes.clear()
        self.axes.set_facecolor("#0f1117")
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        for spine in self.axes.spines.values():
            spine.set_visible(False)

        state = self._states[self._index] if self._index >= 0 else None
        if self._mode == "fixed":
            self._draw_fixed(state if isinstance(state, FixedWindowState) else None)
        else:
            self._draw_variable(
                state if isinstance(state, VariableWindowState) else None
            )
        self.figure.tight_layout(pad=1.5)
        self.draw_idle()

    def _draw_fixed(self, state: FixedWindowState | None) -> None:
        values = self.FIXED_VALUES
        colors = [
            "#6366f1"
            if state is not None and state.left <= index <= state.right
            else "#374151"
            for index in range(len(values))
        ]
        self.axes.bar(range(len(values)), values, color=colors, width=0.72)
        self.axes.set_ylim(0, max(values) + 2)
        self.axes.set_xlim(-0.6, len(values) - 0.4)
        if state is None:
            title = "固定窗口 · 点击“开始”或“单步”观察窗口移动"
        else:
            title = (
                f"窗口 [{state.left}, {state.right}]    "
                f"当前和：{state.window_sum}    最大和：{state.max_sum}"
            )
        self.axes.set_title(title, color="#f9fafb", fontsize=11, pad=16)
        for index, value in enumerate(values):
            self.axes.text(
                index,
                value + 0.15,
                str(value),
                ha="center",
                color="#f9fafb",
                fontsize=10,
            )
        if state is not None:
            self.axes.text(
                0.5,
                0.03,
                state.message,
                transform=self.axes.transAxes,
                ha="center",
                color="#9ca3af",
                fontsize=9,
            )

    def _draw_variable(self, state: VariableWindowState | None) -> None:
        values = self.VARIABLE_VALUES
        colors = []
        for index in range(len(values)):
            if state is not None and state.left <= index <= state.right:
                colors.append("#6366f1")
            else:
                colors.append("#374151")
        self.axes.bar(range(len(values)), values, color=colors, width=0.72)
        self.axes.set_ylim(0, max(values) + 2)
        self.axes.set_xlim(-0.6, len(values) - 0.4)
        if state is None:
            title = f"可变窗口 · 目标和：{self.VARIABLE_TARGET}"
        else:
            best = state.best_length if state.best_length is not None else "—"
            title = (
                f"l = {state.left}    r = {state.right}    "
                f"当前和：{state.window_sum}    最短长度：{best}"
            )
            self.axes.axvline(
                state.left - 0.36,
                color="#22c55e",
                linewidth=2,
                linestyle="--",
            )
            self.axes.text(
                state.left - 0.36,
                1.02,
                "l",
                transform=self.axes.get_xaxis_transform(),
                color="#22c55e",
                ha="center",
                fontweight="bold",
            )
            self.axes.axvline(
                state.right + 0.36,
                color="#ef4444",
                linewidth=2,
                linestyle="--",
            )
            self.axes.text(
                state.right + 0.36,
                1.02,
                "r",
                transform=self.axes.get_xaxis_transform(),
                color="#ef4444",
                ha="center",
                fontweight="bold",
            )
        self.axes.set_title(title, color="#f9fafb", fontsize=11, pad=16)
        for index, value in enumerate(values):
            self.axes.text(
                index,
                value + 0.15,
                str(value),
                ha="center",
                color="#f9fafb",
                fontsize=10,
            )
        if state is not None:
            self.axes.text(
                0.5,
                0.03,
                state.message,
                transform=self.axes.transAxes,
                ha="center",
                color="#9ca3af",
                fontsize=9,
            )
