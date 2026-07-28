"""算法可视化共用的步骤数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class AnimationStep:
    """一帧与界面无关的算法状态。

    ``kind`` 决定画布使用哪种绘制方式，``payload`` 保存该帧所需的状态。
    算法模块只生成步骤，播放、暂停和绘图统一交给 UI 层处理。
    """

    kind: str
    message: str
    values: tuple[int, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)


def step(
    kind: str,
    message: str,
    values: Sequence[int] = (),
    **payload: Any,
) -> AnimationStep:
    """便捷创建不可变的动画步骤。"""

    return AnimationStep(
        kind=kind,
        message=message,
        values=tuple(values),
        payload=payload,
    )
