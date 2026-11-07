"""小步的人设文案库。

所有用户可见的台词都集中在这里，方便统一调语气、避免散落各处。
风格：短、轻、像猫，三个「不」——不催促、不吓你、不记仇。
"""
import random

# 绝对不说的词 / 句式（自我审查）
FORBIDDEN = [
    "你应该", "你必须", "快点", "怎么还不", "别人都",
    "再不做就", "来不及了", "完蛋", "惩罚", "太懒",
    "没用", "放弃吧", "你真", "你看看",
]


def _pick(options):
    return random.choice(options)


def greet(same_day_opens: int, open_count: int) -> str:
    if same_day_opens >= 3:
        return _pick(["又回来啦。我还在。", "没事，回来就行。", "我在。"])
    return _pick(["在的。", "喵。", "来啦。", "我在。"])


def resume(current_step: str) -> str:
    return f"上次你做到「{current_step}」。想接着就接着，不想就歇着。"


def task_ready(title: str, domain: str = "") -> str:
    if domain == "writing":
        return f"好，那我们先打开文档，写三句话就行。"
    return f"好，那我们先做「{title}」。"


def ask_when() -> str:
    return "什么时候开始？"


def scheduled(label: str) -> str:
    return f"行，约在{label}。留在对话页时会轻轻提醒，离开后再回来也可以。"


def ask_delay() -> str:
    return "想约5分钟后，还是10分钟后？"


def commit_prompt() -> str:
    return "就做5分钟。5分钟到了想走随时走，行不行？"


def commit_agree() -> str:
    return "行，开始了。"


def commit_disagree() -> str:
    return "好，那再想想。随时都行。"


def step_next_aside(direction: str) -> str:
    """下一步的温柔旁白。up=加量（状态在线），down=拆细（有点卡）。"""
    if direction == "up":
        return _pick(["状态不错，加点量。", "挺顺的，往前一点。", "在线，再加一小步。"])
    return _pick(["没事，慢一点，拆细点。", "这步有点重，拆开它。", "不赶，我们做小一点。"])


def all_done(title: str, steps_done: int) -> str:
    return "这一小段先到这。想继续再来。"


def gentle_end(what: str) -> str:
    return f"好。今天你{what}。够了。去休息吧。"


def exit_line() -> str:
    return "好，那先到这儿。随时回来。"


def tired_choice() -> str:
    return "累了就先歇歇。想结束可以点「今天到这吧」，也可以把这一步拆小。进度先留着。"


def tired_idle() -> str:
    return "那先歇歇。我在，想做点什么时再来。"


def shrink() -> str:
    return "太重了？行，拆小一点。"


def grow() -> str:
    return "太简单？行，加一点。"


def boundary(direction: str) -> str:
    if direction == "down":
        return "这一步先保持原样，不急。"
    return "再大就太吓人了。就这样，正好。"


def emotion_reply(emotion: str, domain: str = "") -> str:
    if emotion == "焦虑":
        return _pick(["别慌，我们只做眼前这一小步。", "不赶。就一步，很小的一步。", "深呼吸。先做最小那一下。"])
    if emotion == "低落":
        return _pick(["在呢。什么都不想干也行。", "我陪你坐一会儿。", "今天不用勉强。"])
    if emotion == "亢奋":
        return _pick(["趁有劲，我们往前走一点。", "好状态，接着来。", "冲，但不用一次做完。"])
    return ""


def afk_ok() -> str:
    return "行，去刷吧。我不催。"


def afk_due() -> str:
    return "我在这儿，需要了叫我。"


def note_ok() -> str:
    return "记下了。等你想起来再告诉我。"


def note_recall(notes) -> str:
    joined = "、".join(notes)
    return f"对了，你之前记着：「{joined}」。"


def rest_day() -> str:
    return _pick(["行，今天什么都不干也是可以的。", "好，今天就躺着。", "休息也是正经事。"])


def switch_task(old_title: str, new_title: str) -> str:
    return f"好，先放下「{old_title}」，看看「{new_title}」。"


def milestone_week() -> str:
    return "这周你也来过好几次。挺好的。"


# ---------- 新增：摩擦地图 / 跨天交接 / 私人手帐 ----------

def friction_note() -> str:
    """某个领域容易卡时，不点破、不记仇，只轻轻表示"我先拆细一点"。"""
    return "这类任务之前容易卡，我先拆得细一点。"


def handoff_offer(last_step: str) -> str:
    """跨天交接：不硬清零，轻轻问一句要不要接着。"""
    return f"上次你写到「{last_step}」。想接着就接着，不想就翻篇。"


def handoff_resume(step: str) -> str:
    return f"好，接着上次的。「{step}」"


def handoff_dismiss() -> str:
    return "好，那今天做点别的。"


def journal_added() -> str:
    return "记下了。想看的时候去翻翻。"


def journal_deleted() -> str:
    return "好，删掉了。"


def idle_reply() -> str:
    return _pick(["在的。想做什么？", "我在这儿。", "随便说说也行。"])


def remind_step(step: str) -> str:
    return f"我还在。现在这一步：「{step}」"


def switch_ask() -> str:
    return "想换成什么？说“换成……”就行。"
