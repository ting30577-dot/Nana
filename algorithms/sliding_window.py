"""State generators for sliding-window demonstrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence


@dataclass(frozen=True, slots=True)
class WindowState:
    """A single, presentation-independent step of a window algorithm."""

    left: int
    right: int
    window_sum: int
    best_sum: int
    message: str


def fixed_window_steps(values: Sequence[int], size: int) -> Iterator[WindowState]:
    """Yield every state while a fixed-size window moves across ``values``."""

    if size <= 0:
        raise ValueError("Window size must be greater than zero.")
    if size > len(values):
        raise ValueError("Window size cannot exceed the number of values.")

    current_sum = sum(values[:size])
    best_sum = current_sum
    yield WindowState(
        left=0,
        right=size - 1,
        window_sum=current_sum,
        best_sum=best_sum,
        message=f"初始化前 {size} 个元素，窗口和为 {current_sum}",
    )

    for right in range(size, len(values)):
        left = right - size + 1
        outgoing = values[left - 1]
        incoming = values[right]
        current_sum += incoming - outgoing
        best_sum = max(best_sum, current_sum)
        yield WindowState(
            left=left,
            right=right,
            window_sum=current_sum,
            best_sum=best_sum,
            message=f"移出 {outgoing}，加入 {incoming}，窗口和更新为 {current_sum}",
        )

