"""二分查找模式的纯计算步骤。"""

from __future__ import annotations

from typing import Sequence

from algorithms.animation import AnimationStep, step

MAX_VISUAL_DOMAIN_POINTS = 25


def _sample_visual_domain(upper_bound: int) -> tuple[int, ...]:
    """为答案域生成有界的可视化采样点。

    答案二分本身只需要 ``O(log upper_bound)`` 次搜索。可视化不应为了
    展示整个答案域而创建与最大值等长的元组，否则真实题目的大输入会
    把正确的二分实现退化为不可用的内存开销。
    """

    if upper_bound <= MAX_VISUAL_DOMAIN_POINTS:
        return tuple(range(1, upper_bound + 1))

    intervals = MAX_VISUAL_DOMAIN_POINTS - 1
    return tuple(
        1 + (upper_bound - 1) * index // intervals
        for index in range(MAX_VISUAL_DOMAIN_POINTS)
    )


def binary_search_left_steps(
    values: Sequence[int],
    target: int,
) -> list[AnimationStep]:
    """生成左边界二分的半开区间步骤。"""

    snapshot = tuple(values)
    if any(snapshot[index] > snapshot[index + 1] for index in range(len(snapshot) - 1)):
        raise ValueError("二分查找需要非递减数组。")

    left, right = 0, len(snapshot)
    states: list[AnimationStep] = []
    while left < right:
        middle = (left + right) // 2
        if snapshot[middle] < target:
            action = f"{snapshot[middle]} < {target}，舍弃左半区间"
            next_left, next_right = middle + 1, right
        else:
            action = f"{snapshot[middle]} ≥ {target}，保留左侧候选区间"
            next_left, next_right = left, middle
        states.append(
            step(
                "binary_standard",
                action,
                snapshot,
                left=left,
                right=right,
                middle=middle,
                target=target,
                next_left=next_left,
                next_right=next_right,
                phase="search",
            )
        )
        left, right = next_left, next_right

    found = left < len(snapshot) and snapshot[left] == target
    states.append(
        step(
            "binary_standard",
            (
                f"搜索结束，目标的左边界是下标 {left}。"
                if found
                else f"搜索结束，{target} 不在数组中，插入位置是 {left}。"
            ),
            snapshot,
            left=left,
            right=right,
            middle=None,
            target=target,
            result=left,
            found=found,
            phase="done",
        )
    )
    return states


def binary_answer_steps(
    piles: Sequence[int],
    hours_limit: int,
) -> list[AnimationStep]:
    """生成 #875 吃香蕉速度的答案二分步骤。"""

    snapshot = tuple(piles)
    if not snapshot:
        return []
    if hours_limit <= 0 or any(value <= 0 for value in snapshot):
        raise ValueError("香蕉堆和时间限制必须为正数。")
    if hours_limit < len(snapshot):
        raise ValueError("时间限制小于香蕉堆数量，不存在可行速度。")

    def hours_needed(speed: int) -> int:
        return sum((pile + speed - 1) // speed for pile in snapshot)

    left, right = 1, max(snapshot)
    domain = _sample_visual_domain(right)
    feasibility = tuple(hours_needed(speed) <= hours_limit for speed in domain)
    states: list[AnimationStep] = []
    while left < right:
        middle = (left + right) // 2
        needed = hours_needed(middle)
        feasible = needed <= hours_limit
        if feasible:
            next_left, next_right = left, middle
            message = (
                f"速度 {middle} 需要 {needed} 小时，可行；"
                "继续向左寻找更小的可行速度。"
            )
        else:
            next_left, next_right = middle + 1, right
            message = (
                f"速度 {middle} 需要 {needed} 小时，不可行；"
                "答案一定在更大的速度中。"
            )
        states.append(
            step(
                "binary_answer",
                message,
                snapshot,
                domain=domain,
                feasibility=feasibility,
                left=left,
                right=right,
                middle=middle,
                hours=needed,
                hours_limit=hours_limit,
                feasible=feasible,
                next_left=next_left,
                next_right=next_right,
                phase="search",
            )
        )
        left, right = next_left, next_right

    states.append(
        step(
            "binary_answer",
            f"最小可行速度为 {left}。",
            snapshot,
            domain=domain,
            feasibility=feasibility,
            left=left,
            right=right,
            middle=left,
            hours=hours_needed(left),
            hours_limit=hours_limit,
            feasible=True,
            result=left,
            phase="done",
        )
    )
    return states
