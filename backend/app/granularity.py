"""自适应步骤粒度引擎（技术亮点 1）。

根据用户完成单步的耗时，动态调整下一步的大小：
  - 做得快（< fast_threshold 秒）→ 状态在线，下一步加量一档
  - 卡得久（> slow_threshold 秒）→ 启动吃力，下一步拆细一档
  - 中间区间 → 保持当前粒度

这里只判断粒度；动作顺序由step_plan维护，不按不同清单的百分比换位置。
"""
from .config import settings

# 粒度档位：1 细 / 2 中 / 3 粗
_LEVEL_NAMES = {1: "fine", 2: "normal", 3: "coarse"}


def level_name(level: int) -> str:
    return _LEVEL_NAMES[level]


def clamp_level(level: int) -> int:
    return max(1, min(3, level))


def judge(duration_ms: int) -> str:
    """返回 up（加量）/ down（拆细）/ keep（保持）。"""
    seconds = duration_ms / 1000.0
    if seconds < settings.fast_threshold:
        return "up"
    if seconds > settings.slow_threshold:
        return "down"
    return "keep"


def shift_level(cur: int, direction: str) -> int:
    if direction == "up":
        return clamp_level(cur + 1)
    if direction == "down":
        return clamp_level(cur - 1)
    return cur
