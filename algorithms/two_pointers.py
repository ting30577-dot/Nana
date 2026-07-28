"""双指针模式的纯计算步骤。"""

from __future__ import annotations

from typing import Sequence

from algorithms.animation import AnimationStep, step


def collision_steps(
    values: Sequence[int],
    target: int,
) -> list[AnimationStep]:
    """生成有序数组两数之和的对撞指针步骤。"""

    snapshot = tuple(values)
    if any(snapshot[index] > snapshot[index + 1] for index in range(len(snapshot) - 1)):
        raise ValueError("对撞指针示例需要非递减数组。")

    left, right = 0, len(snapshot) - 1
    states: list[AnimationStep] = []
    while left < right:
        total = snapshot[left] + snapshot[right]
        if total == target:
            action = "找到目标"
            next_left, next_right = left, right
            done = True
            message = (
                f"{snapshot[left]} + {snapshot[right]} = {target}，"
                "找到满足条件的两个位置。"
            )
        elif total < target:
            action = "左指针右移"
            next_left, next_right = left + 1, right
            done = False
            message = f"{total} < {target}，需要更大的和，左指针右移。"
        else:
            action = "右指针左移"
            next_left, next_right = left, right - 1
            done = False
            message = f"{total} > {target}，需要更小的和，右指针左移。"

        states.append(
            step(
                "two_collision",
                message,
                snapshot,
                left=left,
                right=right,
                total=total,
                target=target,
                action=action,
                done=done,
            )
        )
        if done:
            break
        left, right = next_left, next_right

    if not states or not states[-1].payload["done"]:
        states.append(
            step(
                "two_collision",
                "左右指针相遇，没有找到满足条件的两个数。",
                snapshot,
                left=left,
                right=right,
                total=None,
                target=target,
                action="搜索结束",
                done=True,
            )
        )
    return states


def fast_slow_cycle_steps(
    values: Sequence[int],
    next_indices: Sequence[int | None],
) -> list[AnimationStep]:
    """生成 Floyd 环检测的快慢指针步骤。"""

    snapshot = tuple(values)
    links = tuple(next_indices)
    if len(snapshot) != len(links):
        raise ValueError("节点与 next 下标数量必须一致。")
    if not snapshot:
        return []
    for next_index in links:
        if next_index is not None and not 0 <= next_index < len(snapshot):
            raise ValueError("next 下标超出节点范围。")

    slow = fast = 0
    states = [
        step(
            "two_fast_slow",
            "slow 和 fast 都从头节点出发。",
            snapshot,
            slow=slow,
            fast=fast,
            links=links,
            met=False,
            move=0,
        )
    ]

    for move in range(1, len(snapshot) * 3 + 1):
        slow_next = links[slow]
        fast_once = links[fast]
        fast_next = links[fast_once] if fast_once is not None else None
        if slow_next is None or fast_next is None:
            states.append(
                step(
                    "two_fast_slow",
                    "fast 到达链表末尾，链表中不存在环。",
                    snapshot,
                    slow=slow if slow_next is None else slow_next,
                    fast=fast if fast_next is None else fast_next,
                    links=links,
                    met=False,
                    done=True,
                    move=move,
                )
            )
            break

        slow, fast = slow_next, fast_next
        met = slow == fast
        states.append(
            step(
                "two_fast_slow",
                (
                    f"第 {move} 步：slow 走 1 格，fast 走 2 格，二者相遇。"
                    if met
                    else f"第 {move} 步：slow 走 1 格，fast 走 2 格。"
                ),
                snapshot,
                slow=slow,
                fast=fast,
                links=links,
                met=met,
                done=met,
                move=move,
            )
        )
        if met:
            break
    return states
