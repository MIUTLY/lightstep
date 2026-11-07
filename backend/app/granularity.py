"""用户主动选择的轻重档位；完成耗时不参与调整。"""

# 粒度档位：1 细 / 2 中 / 3 粗
_LEVEL_NAMES = {1: "fine", 2: "normal", 3: "coarse"}


def level_name(level: int) -> str:
    return _LEVEL_NAMES[level]


def clamp_level(level: int) -> int:
    return max(1, min(3, level))


def shift_level(cur: int, direction: str) -> int:
    if direction == "up":
        return clamp_level(cur + 1)
    if direction == "down":
        return clamp_level(cur - 1)
    return cur
