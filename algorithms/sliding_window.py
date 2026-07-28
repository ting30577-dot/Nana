"""滑动窗口算法的纯计算状态。

这个模块不依赖 PySide6 或 Matplotlib，只负责生成动画需要的每一步状态。
UI 层可以用同一组状态驱动不同的展示方式。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from algorithms.animation import AnimationStep, step


@dataclass(frozen=True, slots=True)
class FixedWindowState:
    """固定窗口动画的一帧。"""

    values: tuple[int, ...]
    left: int
    right: int
    window_sum: int
    max_sum: int
    message: str


@dataclass(frozen=True, slots=True)
class VariableWindowState:
    """可变窗口动画的一帧。

    ``left`` 和 ``right`` 都是数组中的闭区间位置。窗口收缩后，
    ``left`` 可能暂时大于 ``right``，表示当前没有有效窗口。
    """

    values: tuple[int, ...]
    left: int
    right: int
    window_sum: int
    best_length: int | None
    target: int
    phase: str
    message: str


def fixed_window_steps(values: Sequence[int], size: int) -> list[FixedWindowState]:
    """返回固定大小窗口从左到右移动时的状态列表。"""

    if size <= 0:
        raise ValueError("窗口大小必须大于 0。")
    if size > len(values):
        raise ValueError("窗口大小不能超过数组长度。")

    snapshot = tuple(values)
    current_sum = sum(snapshot[:size])
    max_sum = current_sum
    states = [
        FixedWindowState(
            values=snapshot,
            left=0,
            right=size - 1,
            window_sum=current_sum,
            max_sum=max_sum,
            message=f"初始化窗口：[{0}, {size - 1}]，窗口和为 {current_sum}",
        )
    ]

    for right in range(size, len(snapshot)):
        left = right - size + 1
        outgoing = snapshot[left - 1]
        incoming = snapshot[right]
        current_sum += incoming - outgoing
        max_sum = max(max_sum, current_sum)
        states.append(
            FixedWindowState(
                values=snapshot,
                left=left,
                right=right,
                window_sum=current_sum,
                max_sum=max_sum,
                message=(
                    f"右移一格：移出 {outgoing}，加入 {incoming}，"
                    f"当前窗口和为 {current_sum}"
                ),
            )
        )

    return states


def variable_window_steps(
    values: Sequence[int],
    target: int,
) -> list[VariableWindowState]:
    """返回非负数组中“和至少为 target 的最短子数组”状态列表。

    该滑动窗口依赖窗口和随右边界扩张不减、随左边界收缩不增。
    如果包含负数，这个单调性不成立，应改用前缀和等其他方法。
    """

    if target <= 0:
        raise ValueError("目标值必须大于 0。")
    if any(value < 0 for value in values):
        raise ValueError("可变滑动窗口示例只支持非负数组。")
    if not values:
        return []

    snapshot = tuple(values)
    left = 0
    window_sum = 0
    best_length: int | None = None
    states: list[VariableWindowState] = []

    for right, value in enumerate(snapshot):
        window_sum += value
        states.append(
            VariableWindowState(
                values=snapshot,
                left=left,
                right=right,
                window_sum=window_sum,
                best_length=best_length,
                target=target,
                phase="expand",
                message=f"右指针扩张到 {right}，加入 {value}，窗口和为 {window_sum}",
            )
        )

        while window_sum >= target and left <= right:
            current_length = right - left + 1
            if best_length is None or current_length < best_length:
                best_length = current_length
            states.append(
                VariableWindowState(
                    values=snapshot,
                    left=left,
                    right=right,
                    window_sum=window_sum,
                    best_length=best_length,
                    target=target,
                    phase="match",
                    message=(
                        f"窗口和达到 {target}，记录长度 {current_length}，"
                        "尝试收缩左边界"
                    ),
                )
            )

            window_sum -= snapshot[left]
            left += 1
            states.append(
                VariableWindowState(
                    values=snapshot,
                    left=left,
                    right=right,
                    window_sum=window_sum,
                    best_length=best_length,
                    target=target,
                    phase="shrink",
                    message=f"左指针右移到 {left}，窗口和回到 {window_sum}",
                )
            )

    return states


def fixed_window_animation_steps(
    values: Sequence[int],
    size: int,
) -> list[AnimationStep]:
    """将固定窗口计算状态转换为统一动画步骤。"""

    return [
        step(
            "sliding_fixed",
            state.message,
            state.values,
            left=state.left,
            right=state.right,
            window_sum=state.window_sum,
            max_sum=state.max_sum,
            size=size,
        )
        for state in fixed_window_steps(values, size)
    ]


def variable_window_animation_steps(
    values: Sequence[int],
    target: int,
) -> list[AnimationStep]:
    """将可变窗口计算状态转换为统一动画步骤。"""

    return [
        step(
            "sliding_variable",
            state.message,
            state.values,
            left=state.left,
            right=state.right,
            window_sum=state.window_sum,
            best_length=state.best_length,
            target=target,
            phase=state.phase,
        )
        for state in variable_window_steps(values, target)
    ]
