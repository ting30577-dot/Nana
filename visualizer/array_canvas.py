"""Nana 的统一算法动画画布。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, Rectangle
from PySide6.QtCore import QTimer

from algorithms.animation import AnimationStep
from algorithms.binary_search import (
    binary_answer_steps,
    binary_search_left_steps,
)
from algorithms.monotonic_stack import next_greater_steps, trap_rain_steps
from algorithms.prefix_sum import prefix_1d_steps, prefix_2d_steps
from algorithms.sliding_window import (
    fixed_window_animation_steps,
    variable_window_animation_steps,
)
from algorithms.two_pointers import collision_steps, fast_slow_cycle_steps
from ui.theme import PALETTE

matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False


class ArrayCanvas(FigureCanvas):
    """由统一步骤模型驱动的 Matplotlib 画布。

    类名为兼容 v0.1 保留；它现在可以播放全部算法模式。
    """

    FIXED_VALUES = (2, 1, 5, 1, 3, 2)
    FIXED_SIZE = 3
    VARIABLE_VALUES = (2, 3, 1, 2, 4, 3)
    VARIABLE_TARGET = 7

    def __init__(self) -> None:
        self.figure = Figure(figsize=(6, 4), facecolor=PALETTE["app_bg"])
        super().__init__(self.figure)
        self.setMinimumWidth(360)
        self.axes = self.figure.add_subplot(111)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.step_once)
        self._speed = 5
        self._mode = "fixed"
        self._states: list[AnimationStep] = []
        self._index = -1
        self._factories: dict[str, Callable[[], list[AnimationStep]]] = {
            "fixed": lambda: fixed_window_animation_steps(
                self.FIXED_VALUES, self.FIXED_SIZE
            ),
            "variable": lambda: variable_window_animation_steps(
                self.VARIABLE_VALUES, self.VARIABLE_TARGET
            ),
            "two_collision": lambda: collision_steps((1, 2, 4, 6, 10), 8),
            "two_fast_slow": lambda: fast_slow_cycle_steps(
                (3, 2, 0, -4), (1, 2, 3, 1)
            ),
            "prefix_1d": lambda: prefix_1d_steps((2, -1, 3, 5, -2), 1, 3),
            "prefix_2d": lambda: prefix_2d_steps(
                (
                    (3, 0, 1, 4),
                    (5, 6, 3, 2),
                    (1, 2, 0, 1),
                    (4, 1, 0, 1),
                ),
                1,
                1,
                2,
                3,
            ),
            "binary_standard": lambda: binary_search_left_steps(
                (1, 3, 3, 5, 7, 9), 3
            ),
            "binary_answer": lambda: binary_answer_steps((3, 6, 7, 11), 8),
            "stack_next_greater": lambda: next_greater_steps((2, 1, 2, 4, 3)),
            "stack_rain": lambda: trap_rain_steps(
                (0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1)
            ),
        }
        self.set_speed(self._speed)
        self.set_mode("fixed")

    def set_mode(self, mode: str) -> None:
        """切换算法模式并回到初始画面。"""

        if mode not in self._factories:
            raise ValueError(f"未知动画模式：{mode}")
        self._mode = mode
        self._states = self._factories[mode]()
        self.reset()

    def set_speed(self, value: int) -> None:
        self._speed = value
        self._timer.setInterval(max(100, 1100 - value * 100))

    def start(self) -> None:
        if not self._states:
            return
        if self._index >= len(self._states) - 1:
            self._index = -1
        if self._index == -1:
            self.step_once()
        if self._index < len(self._states) - 1:
            self._timer.start()

    def pause(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self.pause()
        self._index = -1
        self._draw_current()

    def step_back(self) -> None:
        """回到上一帧；初始状态不再后退。"""

        self.pause()
        if self._index >= 0:
            self._index -= 1
            self._draw_current()

    def step_once(self) -> None:
        if self._index >= len(self._states) - 1:
            self.pause()
            return
        self._index += 1
        self._draw_current()
        if self._index >= len(self._states) - 1:
            self.pause()

    def _prepare_axes(self) -> None:
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        self.axes.set_facecolor(PALETTE["app_bg"])
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        for spine in self.axes.spines.values():
            spine.set_visible(False)

    def _draw_current(self) -> None:
        self._prepare_axes()
        if self._index < 0:
            self._draw_welcome()
        else:
            state = self._states[self._index]
            renderer = getattr(self, f"_draw_{state.kind}", None)
            if renderer is None:
                self._draw_unknown(state)
            else:
                renderer(state)
        self.figure.tight_layout(pad=1.4)
        self.draw_idle()

    def _draw_welcome(self) -> None:
        self.axes.text(
            0.5,
            0.56,
            "准备开始",
            transform=self.axes.transAxes,
            ha="center",
            va="center",
            color=PALETTE["text"],
            fontsize=18,
            fontweight="bold",
        )
        self.axes.text(
            0.5,
            0.44,
            "点击“开始”或“下一步”观察状态变化",
            transform=self.axes.transAxes,
            ha="center",
            va="center",
            color=PALETTE["muted"],
            fontsize=10,
        )

    def _draw_unknown(self, state: AnimationStep) -> None:
        self.axes.text(
            0.5,
            0.5,
            state.message,
            transform=self.axes.transAxes,
            ha="center",
            color=PALETTE["text"],
        )

    def _message(self, state: AnimationStep, y: float = 0.02) -> None:
        self.axes.text(
            0.5,
            y,
            state.message,
            transform=self.axes.transAxes,
            ha="center",
            va="bottom",
            color=PALETTE["text_soft"],
            fontsize=9,
            wrap=True,
        )

    def _bar_values(
        self,
        values: tuple[int, ...],
        colors: list[str],
        *,
        ylim_extra: float = 2,
    ) -> Any:
        x_values = list(range(len(values)))
        bars = self.axes.bar(x_values, values, color=colors, width=0.7)
        minimum = min(0, min(values, default=0))
        maximum = max(1, max(values, default=1))
        self.axes.set_ylim(minimum - 1, maximum + ylim_extra)
        self.axes.set_xlim(-0.7, len(values) - 0.3)
        for index, value in enumerate(values):
            self.axes.text(
                index,
                value + (0.16 if value >= 0 else -0.45),
                str(value),
                ha="center",
                color=PALETTE["text"],
                fontsize=9,
            )
            self.axes.text(
                index,
                minimum - 0.55,
                str(index),
                ha="center",
                color=PALETTE["subtle"],
                fontsize=8,
            )
        return bars

    def _draw_sliding_fixed(self, state: AnimationStep) -> None:
        left = int(state.payload["left"])
        right = int(state.payload["right"])
        colors = [
            PALETTE["primary"] if left <= index <= right else PALETTE["neutral_bar"]
            for index in range(len(state.values))
        ]
        self._bar_values(state.values, colors)
        self.axes.set_title(
            (
                f"窗口 [{left}, {right}]　当前和：{state.payload['window_sum']}"
                f"　最大和：{state.payload['max_sum']}"
            ),
            color=PALETTE["text"],
            fontsize=11,
            pad=14,
        )
        self._message(state)

    def _draw_sliding_variable(self, state: AnimationStep) -> None:
        left = int(state.payload["left"])
        right = int(state.payload["right"])
        colors = [
            PALETTE["primary"] if left <= index <= right else PALETTE["neutral_bar"]
            for index in range(len(state.values))
        ]
        self._bar_values(state.values, colors)
        best = state.payload.get("best_length")
        self.axes.set_title(
            (
                f"l={left}　r={right}　当前和：{state.payload['window_sum']}"
                f"　最短长度：{best if best is not None else '—'}"
            ),
            color=PALETTE["text"],
            fontsize=11,
            pad=14,
        )
        self.axes.axvline(left - 0.35, color=PALETTE["success"], linewidth=2)
        self.axes.axvline(right + 0.35, color=PALETTE["danger"], linewidth=2)
        self._message(state)

    def _draw_two_collision(self, state: AnimationStep) -> None:
        left = int(state.payload["left"])
        right = int(state.payload["right"])
        colors = [
            PALETTE["info"]
            if index == left
            else PALETTE["danger"]
            if index == right
            else PALETTE["neutral_bar"]
            for index in range(len(state.values))
        ]
        self._bar_values(state.values, colors, ylim_extra=3)
        pointer_y = max(state.values) + 1
        self.axes.text(
            left,
            pointer_y,
            "L",
            color=PALETTE["info"],
            ha="center",
            fontweight="bold",
        )
        self.axes.text(
            right,
            pointer_y,
            "R",
            color=PALETTE["danger"],
            ha="center",
            fontweight="bold",
        )
        total = state.payload.get("total")
        self.axes.set_title(
            (
                f"目标：{state.payload['target']}　"
                f"当前和：{total if total is not None else '—'}　"
                f"{state.payload['action']}"
            ),
            color=PALETTE["text"],
            fontsize=11,
            pad=14,
        )
        self._message(state)

    def _draw_two_fast_slow(self, state: AnimationStep) -> None:
        values = state.values
        links = state.payload["links"]
        slow = int(state.payload["slow"])
        fast = int(state.payload["fast"])
        met = bool(state.payload.get("met"))
        positions = [(index * 1.55, 0.5 + (0.75 if index == 3 else 0)) for index in range(len(values))]
        self.axes.set_xlim(-0.8, max(x for x, _ in positions) + 0.9)
        self.axes.set_ylim(-0.6, 2.5)
        for index, ((x_pos, y_pos), value) in enumerate(zip(positions, values)):
            if met and index == slow:
                color = PALETTE["primary_strong"]
            elif index == slow:
                color = PALETTE["info"]
            elif index == fast:
                color = PALETTE["danger"]
            else:
                color = PALETTE["neutral_bar"]
            circle = self.axes.scatter(
                [x_pos],
                [y_pos],
                s=1050,
                color=color,
                edgecolor=PALETTE["border_strong"],
                zorder=3,
            )
            circle.set_clip_on(False)
            self.axes.text(
                x_pos, y_pos, str(value), ha="center", va="center",
                color=PALETTE["text"], fontweight="bold", zorder=4
            )
            next_index = links[index]
            if next_index is not None:
                next_x, next_y = positions[next_index]
                arc = -0.45 if next_index < index else 0.08
                arrow = FancyArrowPatch(
                    (x_pos + 0.28, y_pos),
                    (next_x - 0.34 if next_x > x_pos else next_x + 0.34, next_y),
                    arrowstyle="-|>",
                    mutation_scale=12,
                    color=PALETTE["subtle"],
                    connectionstyle=f"arc3,rad={arc}",
                    linewidth=1.4,
                    zorder=1,
                )
                self.axes.add_patch(arrow)
        slow_x, slow_y = positions[slow]
        fast_x, fast_y = positions[fast]
        self.axes.text(
            slow_x,
            slow_y + 0.55,
            "slow",
            color=PALETTE["info"],
            ha="center",
        )
        self.axes.text(
            fast_x,
            fast_y - 0.62,
            "fast",
            color=PALETTE["danger"],
            ha="center",
        )
        self.axes.set_title(
            "快慢指针 · Floyd 环检测" + (" · 相遇，存在环" if met else ""),
            color=PALETTE["text"],
            fontsize=11,
            pad=12,
        )
        self._message(state)

    def _draw_prefix_1d(self, state: AnimationStep) -> None:
        values = state.values
        prefix = tuple(state.payload["prefix"])
        built = int(state.payload["built"])
        phase = state.payload["phase"]
        self.axes.set_xlim(-0.8, max(len(values), len(prefix)) - 0.2)
        self.axes.set_ylim(-2.2, 2.2)
        self.axes.axhline(0, color=PALETTE["border"], linewidth=1)
        for index, value in enumerate(values):
            query = (
                phase != "build"
                and state.payload["query_left"] <= index <= state.payload["query_right"]
            )
            color = PALETTE["primary"] if query else PALETTE["neutral_bar"]
            self.axes.add_patch(Rectangle((index - 0.38, 0.42), 0.76, 0.7, color=color))
            self.axes.text(
                index,
                0.77,
                str(value),
                ha="center",
                va="center",
                color=PALETTE["on_accent"],
            )
            self.axes.text(
                index,
                1.35,
                f"nums[{index}]",
                ha="center",
                color=PALETTE["muted"],
                fontsize=8,
            )
        for index, value in enumerate(prefix):
            is_built = index <= built
            selected = phase != "build" and index in {
                state.payload.get("prefix_left"),
                state.payload.get("prefix_right"),
            }
            color = (
                PALETTE["success"]
                if selected
                else PALETTE["surface_strong"]
                if is_built
                else PALETTE["surface_alt"]
            )
            self.axes.add_patch(Rectangle((index - 0.38, -1.02), 0.76, 0.7, color=color))
            self.axes.text(
                index, -0.67, str(value) if is_built else "·",
                ha="center",
                va="center",
                color=PALETTE["on_accent"] if is_built else PALETTE["subtle"],
            )
            self.axes.text(
                index,
                -1.28,
                f"p[{index}]",
                ha="center",
                color=PALETTE["muted"],
                fontsize=8,
            )
        title = "一维前缀和 · 同步构建"
        if phase == "query":
            title = f"区间和 = {state.payload['result']}"
        elif phase == "explain":
            title = "为什么相减：去掉区间左侧的累计和"
        self.axes.set_title(title, color=PALETTE["text"], fontsize=11, pad=12)
        self._message(state, 0.01)

    def _draw_prefix_2d(self, state: AnimationStep) -> None:
        matrix = state.payload["matrix"]
        phase = state.payload["phase"]
        rows, columns = len(matrix), len(matrix[0])
        self.axes.set_xlim(-0.8, columns - 0.2)
        self.axes.set_ylim(rows - 0.2, -1.05)
        query = state.payload["query"]
        current = state.payload.get("current")
        for row in range(rows):
            for column in range(columns):
                in_query = (
                    phase == "query"
                    and query[0] <= row <= query[2]
                    and query[1] <= column <= query[3]
                )
                is_current = current == (row, column)
                color = (
                    PALETTE["success"]
                    if in_query
                    else PALETTE["primary"]
                    if is_current
                    else PALETTE["surface_strong"]
                )
                self.axes.add_patch(
                    Rectangle((column - 0.42, row - 0.42), 0.84, 0.84, color=color)
                )
                self.axes.text(
                    column, row, str(matrix[row][column]),
                    ha="center",
                    va="center",
                    color=PALETTE["on_accent"],
                    fontsize=10,
                )
        title = (
            f"二维区域和 = {state.payload['result']}"
            if phase == "query"
            else "二维前缀和 · 逐格构建"
        )
        self.axes.set_title(title, color=PALETTE["text"], fontsize=11, pad=12)
        self._message(state)

    def _draw_binary_standard(self, state: AnimationStep) -> None:
        left = int(state.payload["left"])
        right = int(state.payload["right"])
        middle = state.payload.get("middle")
        colors = []
        for index in range(len(state.values)):
            if index == middle:
                colors.append(PALETTE["warning"])
            elif left <= index < right:
                colors.append(PALETTE["primary"])
            else:
                colors.append(PALETTE["neutral_bar"])
        self._bar_values(state.values, colors, ylim_extra=3)
        if middle is not None:
            self.axes.text(
                middle, max(state.values) + 1, "mid",
                color=PALETTE["warning"],
                ha="center",
                fontweight="bold",
            )
        self.axes.set_title(
            f"搜索区间 [{left}, {right})　目标：{state.payload['target']}",
            color=PALETTE["text"],
            fontsize=11,
            pad=14,
        )
        self._message(state)

    def _draw_binary_answer(self, state: AnimationStep) -> None:
        domain = state.payload["domain"]
        feasibility = state.payload["feasibility"]
        middle = int(state.payload["middle"])
        colors = [
            PALETTE["success"] if feasible else PALETTE["danger"]
            for feasible in feasibility
        ]
        self.axes.scatter(domain, [0] * len(domain), c=colors, s=180, zorder=2)
        self.axes.axvline(
            middle,
            color=PALETTE["warning"],
            linewidth=2,
            linestyle="--",
        )
        self.axes.text(
            middle,
            0.38,
            f"mid={middle}",
            color=PALETTE["warning"],
            ha="center",
        )
        self.axes.set_xlim(min(domain) - 0.7, max(domain) + 0.7)
        self.axes.set_ylim(-1.0, 1.1)
        if len(domain) <= 9:
            ticks = domain
        else:
            last = len(domain) - 1
            ticks = tuple(domain[last * index // 8] for index in range(9))
        self.axes.set_xticks(ticks)
        self.axes.tick_params(axis="x", colors=PALETTE["muted"], labelsize=8)
        self.axes.set_title(
            (
                f"答案二分 · {state.payload['hours']} 小时 / "
                f"限制 {state.payload['hours_limit']} 小时"
            ),
            color=PALETTE["text"],
            fontsize=11,
            pad=12,
        )
        self._message(state)

    def _stack_sidebar(self, stack: tuple[int, ...], values: tuple[int, ...]) -> None:
        x_pos = len(values) + 0.65
        self.axes.text(
            x_pos,
            max(values) + 1.15,
            "栈顶",
            color=PALETTE["muted"],
            ha="center",
            fontsize=8,
        )
        for level, index in enumerate(reversed(stack)):
            y_pos = max(values) - level * 0.72
            self.axes.add_patch(
                Rectangle(
                    (x_pos - 0.38, y_pos - 0.25),
                    0.76,
                    0.5,
                    color=PALETTE["info"],
                )
            )
            self.axes.text(
                x_pos, y_pos, f"{values[index]} ({index})",
                color=PALETTE["on_accent"],
                ha="center",
                va="center",
                fontsize=8,
            )
        self.axes.text(
            x_pos,
            -0.4,
            "单调栈",
            color=PALETTE["muted"],
            ha="center",
            fontsize=9,
        )

    def _draw_stack_next_greater(self, state: AnimationStep) -> None:
        current = state.payload.get("current")
        popped = state.payload.get("popped")
        colors = [
            PALETTE["warning"]
            if index == current
            else PALETTE["danger"]
            if index == popped
            else PALETTE["neutral_bar"]
            for index in range(len(state.values))
        ]
        self._bar_values(state.values, colors, ylim_extra=3)
        self.axes.set_xlim(-0.7, len(state.values) + 1.6)
        self._stack_sidebar(tuple(state.payload["stack"]), state.values)
        if popped is not None and current is not None:
            self.axes.annotate(
                "",
                xy=(current, state.values[current] + 0.25),
                xytext=(popped, state.values[popped] + 0.25),
                arrowprops={
                    "arrowstyle": "->",
                    "color": PALETTE["danger"],
                    "lw": 2,
                },
            )
        self.axes.set_title(
            "下一个更大元素 · 从左向右",
            color=PALETTE["text"],
            fontsize=11,
            pad=12,
        )
        self._message(state)

    def _draw_stack_rain(self, state: AnimationStep) -> None:
        current = state.payload.get("current")
        popped = state.payload.get("popped")
        colors = [
            PALETTE["warning"]
            if index == current
            else PALETTE["danger"]
            if index == popped
            else PALETTE["neutral_bar"]
            for index in range(len(state.values))
        ]
        self._bar_values(state.values, colors, ylim_extra=3)
        for left, right, bottom_height, bounded_height in state.payload["segments"]:
            if bounded_height <= 0:
                continue
            self.axes.add_patch(
                Rectangle(
                    (left + 0.35, bottom_height),
                    right - left - 0.7,
                    bounded_height,
                    color=PALETTE["info"],
                    alpha=0.38,
                )
            )
        self.axes.set_xlim(-0.7, len(state.values) + 1.6)
        self._stack_sidebar(tuple(state.payload["stack"]), state.values)
        self.axes.set_title(
            f"接雨水 · 当前累计：{state.payload['water']}",
            color=PALETTE["text"],
            fontsize=11,
            pad=12,
        )
        self._message(state)
