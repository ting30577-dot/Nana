"""单调栈模式的纯计算步骤，统一采用从左向右遍历。"""

from __future__ import annotations

from typing import Sequence

from algorithms.animation import AnimationStep, step


def next_greater_steps(values: Sequence[int]) -> list[AnimationStep]:
    """生成下一个更大元素的单调递减栈步骤。"""

    snapshot = tuple(values)
    result = [-1] * len(snapshot)
    stack: list[int] = []
    states: list[AnimationStep] = []

    for index, value in enumerate(snapshot):
        states.append(
            step(
                "stack_next_greater",
                f"检查 nums[{index}] = {value}。",
                snapshot,
                current=index,
                stack=tuple(stack),
                result=tuple(result),
                popped=None,
                phase="inspect",
            )
        )
        while stack and snapshot[stack[-1]] < value:
            popped = stack.pop()
            result[popped] = value
            states.append(
                step(
                    "stack_next_greater",
                    (
                        f"{value} 大于栈顶 {snapshot[popped]}，下标 {popped} 出栈；"
                        f"它的下一个更大值就是 {value}。"
                    ),
                    snapshot,
                    current=index,
                    stack=tuple(stack),
                    result=tuple(result),
                    popped=popped,
                    trigger=index,
                    phase="pop",
                )
            )
        stack.append(index)
        states.append(
            step(
                "stack_next_greater",
                f"下标 {index} 入栈，栈内数值保持单调递减。",
                snapshot,
                current=index,
                stack=tuple(stack),
                result=tuple(result),
                popped=None,
                phase="push",
            )
        )

    states.append(
        step(
            "stack_next_greater",
            f"遍历结束，栈中剩余元素右侧没有更大值。结果：{result}",
            snapshot,
            current=None,
            stack=tuple(stack),
            result=tuple(result),
            popped=None,
            phase="done",
        )
    )
    return states


def trap_rain_steps(heights: Sequence[int]) -> list[AnimationStep]:
    """生成单调栈接雨水的步骤。"""

    snapshot = tuple(heights)
    if any(height < 0 for height in snapshot):
        raise ValueError("柱子高度不能为负数。")

    stack: list[int] = []
    total_water = 0
    states: list[AnimationStep] = []
    water_segments: list[tuple[int, int, int, int]] = []

    for index, height in enumerate(snapshot):
        states.append(
            step(
                "stack_rain",
                f"来到下标 {index}，当前柱高为 {height}。",
                snapshot,
                current=index,
                stack=tuple(stack),
                water=total_water,
                segments=tuple(water_segments),
                popped=None,
                phase="inspect",
            )
        )
        while stack and snapshot[stack[-1]] < height:
            bottom = stack.pop()
            if not stack:
                states.append(
                    step(
                        "stack_rain",
                        f"柱 {bottom} 出栈，但左侧没有边界，不能形成积水。",
                        snapshot,
                        current=index,
                        stack=tuple(stack),
                        water=total_water,
                        segments=tuple(water_segments),
                        popped=bottom,
                        phase="pop",
                    )
                )
                break

            left = stack[-1]
            width = index - left - 1
            bounded_height = min(snapshot[left], height) - snapshot[bottom]
            added = width * bounded_height
            total_water += added
            water_segments.append((left, index, snapshot[bottom], bounded_height))
            states.append(
                step(
                    "stack_rain",
                    (
                        f"柱 {bottom} 出栈，左右边界为 {left} 和 {index}；"
                        f"宽 {width} × 高 {bounded_height}，新增积水 {added}。"
                    ),
                    snapshot,
                    current=index,
                    stack=tuple(stack),
                    water=total_water,
                    segments=tuple(water_segments),
                    popped=bottom,
                    left_boundary=left,
                    added=added,
                    phase="water",
                )
            )
        stack.append(index)
        states.append(
            step(
                "stack_rain",
                f"下标 {index} 入栈，当前累计积水为 {total_water}。",
                snapshot,
                current=index,
                stack=tuple(stack),
                water=total_water,
                segments=tuple(water_segments),
                popped=None,
                phase="push",
            )
        )

    states.append(
        step(
            "stack_rain",
            f"遍历完成，总积水量为 {total_water}。",
            snapshot,
            current=None,
            stack=tuple(stack),
            water=total_water,
            segments=tuple(water_segments),
            popped=None,
            phase="done",
        )
    )
    return states
