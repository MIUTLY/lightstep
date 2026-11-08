"""保守识别收尾：整句表达才触发，不从任意上下文截取关键词。"""
import re
from typing import Literal

# 仅接受这些完整分句；未知补充、问句、否定结束、条件和引用均留给普通对话。
_END = re.compile(
    r"(?:请|那就?)?(?:(?:(?:我|我们)(?:想|要)?)?(?:今天|现在)?(?:就)?(?:先)?"
    r"(?:到这(?:儿|里)?|到此(?:为止)?|结束(?:当前任务|这个任务|这次任务|任务)?|收工|温柔收尾|够了|不做了|不想做了|不干了)"
    r"(?:吧|了)?|(?:我)?(?:今天)?(?:什么都不想干|不想干了)|(?:我)?今天(?:就)?休息(?:一天)?)"
)
_TIRED = re.compile(
    r"(?:(?:我|这步|这一步|这个任务)?(?:有点|有些|太|很|好|真的|实在|已经|感觉)?"
    r"(?:累了?|累坏了|疲惫了?|没力气了?|做不动了|学不动了|撑不住了)"
    r"|(?:我)?(?:想|想要|要)?先?(?:休息|歇)(?:一下|一会儿?|会儿?)?)(?:吧)?"
)
_FILLERS = {"好", "好的", "行", "那", "嗯", "小步", "谢谢", "谢谢你", "辛苦了"}


def ending_intent(text: str) -> Literal["end", "tired"] | None:
    clauses = [part.strip() for part in re.split(r"[，,。.!！；;]+", text.strip()) if part.strip()]
    intents = []
    for clause in clauses:
        if clause in _FILLERS:
            continue
        if _END.fullmatch(clause):
            intents.append("end")
        elif _TIRED.fullmatch(clause):
            intents.append("tired")
        else:
            return None
    # 疲惫+明确收尾可直接结束；疲惫本身不足以证明用户想删掉当前任务。
    if "end" in intents:
        return "end"
    if intents:
        return "tired"
    return None
