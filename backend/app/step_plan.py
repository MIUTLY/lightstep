"""稳定的有序动作队列：粒度变化不再切换到另一套任务清单。"""
from copy import deepcopy
import hashlib
import re
from uuid import uuid4

from .granularity import level_name

PLAN_KEY = "_step_plan"
_NUMBERS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9}
_COUNT = re.compile(r"(?<![第0-9A-Za-z零一二两三四五六七八九十百千万亿.．/／-])([0-9]+|[零一二两三四五六七八九十百千万亿]+)(\s*(?:个单词|个词|句话|页|道题|分钟|样东西))")


def _number(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    if text in _NUMBERS:
        return _NUMBERS[text]
    if text.count("十") == 1:
        left, right = text.split("十")
        if (not left or left in _NUMBERS) and (not right or right in _NUMBERS):
            return _NUMBERS.get(left, 1) * 10 + _NUMBERS.get(right, 0)
    return None


def split_action(text: str) -> list[str] | None:
    """只做可追溯的数量拆分或并列动作拆分，无法确定时不改写。"""
    if any(word in text for word in ("如果", "假如", "否则", "不要", "不用", "不必")):
        return None
    if re.search(r"\d\s*[,，.．/／-]\s*\d", text) or "分之" in text:
        return None
    parts = [part.strip() for part in re.split(r"[，,；;]", text) if part.strip()]
    qualifiers = ("先不", "不管", "无需", "就行", "即可", "随意", "随便")
    if len(parts) > 1 and not all(part.startswith(qualifiers) for part in parts[1:]):
        # 先保留不同动作的顺序，不能把“写三句，再读一遍”拆成两次读一遍。
        return [parts[0], "，".join(parts[1:])]
    counts = list(_COUNT.finditer(text))
    if len(counts) == 1:
        match = counts[0]
        number = _number(match.group(1))
        # 第5页是位置，不是五页工作量。
        ordinal = text[:match.start()].rstrip().endswith("第")
        if number and number > 1 and not ordinal:
            a, b = match.span(1)
            return [text[:a] + "1" + text[b:], text[:a] + str(number - 1) + text[b:]]
    return None


def _plan(steps: list[str], identity: str) -> dict:
    return {"version": 1, "id": identity,
            "units": [{"id": f"s{i}", "text": text} for i, text in enumerate(steps)],
            "batch_end": 1}


def new_plan(levels: dict, level: int) -> dict:
    result = deepcopy(levels)
    # normal 是本次任务的主路线；fine/coarse 仅保留兼容，不作为替代路线。
    result[PLAN_KEY] = _plan(list(levels["normal"]), uuid4().hex)
    prepare_step(result, 0, level)
    return result


def ensure_plan(task: dict) -> dict:
    """旧任务只保留当时的清单和游标，不倒推已做过什么。"""
    import json
    levels = json.loads(task["levels_json"])
    if PLAN_KEY not in levels:
        steps = levels.get(level_name(task["level"])) or [task["title"]]
        date = task.get("date") or task.get("saved_date") or ""
        identity = hashlib.sha256((task["title"] + date + task["levels_json"]).encode()).hexdigest()[:24]
        levels[PLAN_KEY] = _plan(list(steps), "legacy-" + identity)
        levels[PLAN_KEY]["batch_end"] = task["current_idx"] + 1
    return levels


def prepare_step(levels: dict, cursor: int, level: int) -> None:
    plan = levels[PLAN_KEY]
    units = plan["units"]
    while level == 1 and cursor < len(units):
        unit = units[cursor]
        parts = split_action(unit["text"])
        if parts:
            units[cursor:cursor + 1] = [
                {"id": unit["id"] + f".{i}", "text": part} for i, part in enumerate(parts)]
        else:
            break
    # 粗档最多合并两个相邻动作，仍在文字中保留二者的执行顺序。
    plan["batch_end"] = min(cursor + (2 if level == 3 else 1), len(units))


def displayed_units(levels: dict, cursor: int) -> list[dict]:
    plan = levels[PLAN_KEY]
    end = plan.get("batch_end", cursor + 1)
    if end <= cursor or end > len(plan["units"]):
        end = min(cursor + 1, len(plan["units"]))
    return plan["units"][cursor:end]


def current_text(task: dict) -> str:
    levels = ensure_plan(task)
    return "；接着".join(unit["text"] for unit in displayed_units(levels, task["current_idx"])) or task["title"]


def step_id(task: dict) -> str:
    levels = ensure_plan(task)
    ids = "+".join(unit["id"] for unit in displayed_units(levels, task["current_idx"]))
    return levels[PLAN_KEY]["id"] + ":" + ids


def next_cursor(levels: dict, cursor: int) -> int:
    """只消费用户刚才看见的动作，不根据耗时重新计算已完成内容。"""
    return cursor + len(displayed_units(levels, cursor))


def is_finished(levels: dict, cursor: int) -> bool:
    return cursor >= len(levels[PLAN_KEY]["units"])
