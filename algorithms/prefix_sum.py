"""前缀和模式的纯计算步骤。"""

from __future__ import annotations

from typing import Sequence

from algorithms.animation import AnimationStep, step


def prefix_1d_steps(
    values: Sequence[int],
    query_left: int,
    query_right: int,
) -> list[AnimationStep]:
    """构建一维前缀和并演示闭区间查询。"""

    snapshot = tuple(values)
    if not snapshot:
        return []
    if not 0 <= query_left <= query_right < len(snapshot):
        raise ValueError("查询区间超出数组范围。")

    prefix = [0] * (len(snapshot) + 1)
    states: list[AnimationStep] = []
    for index, value in enumerate(snapshot):
        prefix[index + 1] = prefix[index] + value
        states.append(
            step(
                "prefix_1d",
                (
                    f"prefix[{index + 1}] = prefix[{index}] + nums[{index}] "
                    f"= {prefix[index]} + {value} = {prefix[index + 1]}"
                ),
                snapshot,
                prefix=tuple(prefix),
                built=index + 1,
                phase="build",
                query_left=query_left,
                query_right=query_right,
            )
        )

    right_prefix = query_right + 1
    left_prefix = query_left
    result = prefix[right_prefix] - prefix[left_prefix]
    states.append(
        step(
            "prefix_1d",
            (
                f"prefix[{right_prefix}] 包含 nums[0..{query_right}]，"
                f"prefix[{left_prefix}] 是区间左侧需要去掉的部分。"
            ),
            snapshot,
            prefix=tuple(prefix),
            built=len(snapshot),
            phase="explain",
            query_left=query_left,
            query_right=query_right,
            prefix_left=left_prefix,
            prefix_right=right_prefix,
            result=result,
        )
    )
    states.append(
        step(
            "prefix_1d",
            (
                f"区间 [{query_left}, {query_right}] 的和 = "
                f"prefix[{right_prefix}] - prefix[{left_prefix}] = "
                f"{prefix[right_prefix]} - {prefix[left_prefix]} = {result}"
            ),
            snapshot,
            prefix=tuple(prefix),
            built=len(snapshot),
            phase="query",
            query_left=query_left,
            query_right=query_right,
            prefix_left=left_prefix,
            prefix_right=right_prefix,
            result=result,
        )
    )
    return states


def prefix_2d_steps(
    matrix: Sequence[Sequence[int]],
    top: int,
    left: int,
    bottom: int,
    right: int,
) -> list[AnimationStep]:
    """构建二维前缀和并演示矩形区域查询。"""

    snapshot = tuple(tuple(row) for row in matrix)
    if not snapshot:
        return []
    columns = len(snapshot[0])
    if any(len(row) != columns for row in snapshot):
        raise ValueError("矩阵的每一行必须等长。")
    if columns == 0:
        return []
    rows = len(snapshot)
    if not (0 <= top <= bottom < rows and 0 <= left <= right < columns):
        raise ValueError("查询矩形超出矩阵范围。")

    prefix = [[0] * (columns + 1) for _ in range(rows + 1)]
    states: list[AnimationStep] = []
    for row in range(rows):
        for column in range(columns):
            prefix[row + 1][column + 1] = (
                prefix[row][column + 1]
                + prefix[row + 1][column]
                - prefix[row][column]
                + snapshot[row][column]
            )
            states.append(
                step(
                    "prefix_2d",
                    (
                        f"计算 prefix[{row + 1}][{column + 1}]："
                        "上方 + 左侧 - 重复部分 + 当前元素。"
                    ),
                    matrix=snapshot,
                    prefix=tuple(tuple(line) for line in prefix),
                    current=(row, column),
                    phase="build",
                    query=(top, left, bottom, right),
                )
            )

    result = (
        prefix[bottom + 1][right + 1]
        - prefix[top][right + 1]
        - prefix[bottom + 1][left]
        + prefix[top][left]
    )
    states.append(
        step(
            "prefix_2d",
            (
                f"区域 ({top},{left}) 到 ({bottom},{right}) 的和为 {result}："
                "大矩形减去上方和左侧，再加回被重复减去的部分。"
            ),
            matrix=snapshot,
            prefix=tuple(tuple(line) for line in prefix),
            current=None,
            phase="query",
            query=(top, left, bottom, right),
            result=result,
        )
    )
    return states
