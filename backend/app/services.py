"""核心编排：把所有接口串成一条温柔的任务流。

职责：
  - 意图识别（关键词规则，离线可用）
  - 状态机：idle → ready → committing → executing → done
  - 自适应粒度、摩擦地图、跨天交接、便签与提醒
  - 回执图片及回执留言由客户端保存，不写入服务端
"""
import json
from datetime import datetime, timedelta

from . import persona
from .db import db
from .decompose import domain_of
from .granularity import judge, shift_level, map_progress, level_name
from .llm import llm
from .schemas import Reply, TaskView

# ---------- 意图关键词 ----------

_NEGATIVE = ["不想", "不要", "算了", "不用", "不做", "不做了"]
_GOAL_INTENT = ["想", "要", "得", "该", "准备", "打算", "试试", "试着", "今晚", "今晚要", "开始做"]
_GOAL_VERBS = ["刷题", "写", "背", "读", "看", "学", "复习", "整理", "收拾", "跑步", "健身",
               "运动", "练", "做题", "改", "画", "做"]
_EXIT = ["不做了", "今天到这", "到此", "结束", "收工", "够了", "温柔收尾", "不想做了", "先到这"]
_TOO_BIG = ["太多", "太重", "太大", "好难", "太难", "做不完", "好多", "缩小", "拆细", "太累", "有点难"]
_TOO_EASY = ["太简单", "太容易", "加量", "加一点", "不够", "太少", "放大", "太轻松"]
_NOTE = ["记一下", "记个", "记得", "别忘", "提醒我", "备忘", "记下", "帮我记"]
_AFK = ["手机", "视频", "打游戏", "玩游戏", "抖音", "短视频", "刷", "走神", "发呆", "摸鱼", "躺一会儿"]
_REST = ["什么都不想干", "不想干", "今天休息", "放假", "躺平", "摆烂", "休息一天", "今天不想", "不干了"]
_SWITCH = ["换个任务", "换成", "改做", "不做这个", "换一个", "换件事", "换个事"]
_CONTINUE = ["接着", "继续"]

_LEAD_FILLERS = sorted(
    ["那我试试", "我试试", "我试", "试试看", "试着", "我想", "我想做", "我要", "我准备", "我打算",
     "我们", "我们来", "今晚", "今天", "准备", "打算", "换个任务", "换件事", "换成", "改做",
     "好", "那", "就", "先", "去", "来", "吧"],
    key=len, reverse=True,
)


# ---------- 小工具 ----------

def _has_any(text: str, words) -> bool:
    return any(w in text for w in words)


def _levels_of(task: dict) -> dict:
    return json.loads(task["levels_json"])


def _current_step_text(task: dict) -> str:
    levels = _levels_of(task)
    steps = levels.get(level_name(task["level"]), [])
    if not steps:
        return task["title"]
    idx = min(task["current_idx"], len(steps) - 1)
    return steps[idx]


def _task_view(task: dict) -> TaskView:
    return TaskView(
        title=task["title"],
        current_step=_current_step_text(task),
        steps_done=task["steps_done"],
        granularity=level_name(task["level"]),
        state=task["state"],
    )


def _buttons_for(task) -> list[str]:
    if not task:
        return []
    return {
        "ready": ["现在开始", "待会儿", "今天不做"],
        "committing": ["行", "再想想"],
        "executing": ["完成这一步", "太重了", "今天到这吧"],
    }.get(task["state"], [])


def _summary_text(summary: dict) -> str:
    if not summary["titles"]:
        return "今天还没做什么，也没关系。"
    return f"今天动了「{'」「'.join(summary['titles'])}」，一共 {summary['steps_done']} 小步。"


def _describe_state(task) -> str:
    if not task:
        return "用户空闲，没有进行中的任务。"
    step = _current_step_text(task)
    return (f"正在做「{task['title']}」，当前步骤「{step}」，"
            f"已完成 {task['steps_done']} 步，状态 {task['state']}。")


def _extract_title(text: str) -> str:
    t = text.strip()
    changed = True
    while changed:
        changed = False
        # 每轮先剥掉开头标点，避免"好，那我试试…"里的逗号卡住语气词剥离
        t = t.lstrip("，。！？、,.!? ")
        for w in _LEAD_FILLERS:
            if t.startswith(w):
                t = t[len(w):]
                changed = True
                break
    t = t.strip("，。！？、,.!? ")
    return t or "这件事"


def _is_goal(text: str) -> bool:
    if _has_any(text, _NEGATIVE):
        return False
    if any(v in text for v in _GOAL_VERBS):
        return True
    return any(w in text for w in _GOAL_INTENT)


def _is_recent(date_str: str) -> bool:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return False
    return (datetime.now().date() - d).days <= 7


def _weekly_milestone(visit_dates: list) -> bool:
    week_start = (datetime.now().date() - timedelta(days=7)).isoformat()
    recent = {d for d in (visit_dates or []) if d >= week_start}
    return len(recent) in (3, 5, 7)


def _handoff_last_step(handoff: dict) -> str:
    levels = json.loads(handoff["levels_json"])
    steps = levels.get(level_name(handoff["level"]), [])
    if not steps:
        return handoff["title"]
    idx = min(handoff["current_idx"], len(steps) - 1)
    return steps[idx]


# ---------- 会话 ----------

def handle_open(user_id: str) -> Reply:
    info = db.open_session(user_id)
    task = db.get_active_task(user_id)
    due = db.due_reminders(user_id)

    handoff_reply = None
    if not task and info["same_day_opens"] == 1:
        handoff = db.get_handoff(user_id)
        if handoff:
            if not _is_recent(handoff["saved_date"]):
                db.clear_handoff(user_id)
            else:
                handoff_reply = persona.handoff_offer(_handoff_last_step(handoff))

    if task:
        step = _current_step_text(task)
        return Reply(reply=persona.resume(step), state=task["state"], task=_task_view(task),
                     buttons=_buttons_for(task), due_reminders=due)

    if handoff_reply:
        return Reply(reply=handoff_reply, state="idle", buttons=["接着做", "翻篇"], due_reminders=due)

    msgs = [persona.greet(info["same_day_opens"], info["open_count"])]
    if info["new_day"] and _weekly_milestone(info["visit_dates"]):
        msgs.append(persona.milestone_week())
    return Reply(reply=" ".join(msgs), state="idle", due_reminders=due, buttons=[])


def handle_chat(user_id: str, message: str) -> Reply:
    text = (message or "").strip()
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not text:
        return Reply(reply=persona.afk_due(), state=task["state"] if task else "idle",
                     task=_task_view(task) if task else None, buttons=_buttons_for(task))
    return _chat_reply(user_id, text)


def _chat_reply(user_id: str, text: str) -> Reply:
    task = db.get_active_task(user_id)

    # 1. 接着上次（跨天交接）
    if _has_any(text, _CONTINUE) and db.get_handoff(user_id):
        return resume_handoff(user_id)

    # 2. 温柔收尾
    if task and _has_any(text, _EXIT):
        return _gentle_end(user_id, task)

    # 3. 走神记笔记
    if _has_any(text, _NOTE):
        return _note(user_id, text)

    # 4. 今天什么都不想干
    if _has_any(text, _REST):
        return _rest_day(user_id)

    # 5. 换件事
    if _has_any(text, _SWITCH):
        return _switch_task(user_id, text)

    # 6. 太重 / 太简单（有任务时）
    if task and _has_any(text, _TOO_BIG):
        return handle_resize(user_id, "smaller")
    if task and _has_any(text, _TOO_EASY):
        return handle_resize(user_id, "bigger")

    # 7. 想做事（新任务 / 替换当前）
    if _is_goal(text):
        return _create_task(user_id, text)

    # 8. 发呆 / 摸鱼
    if _has_any(text, _AFK):
        return _afk(user_id)

    # 9. 兜底：情绪 or 闲聊
    emotion = llm.detect_emotion(text)
    if emotion != "正常":
        return Reply(reply=persona.emotion_reply(emotion),
                     state=task["state"] if task else "idle",
                     task=_task_view(task) if task else None, buttons=_buttons_for(task))
    llm_reply = llm.reply(_describe_state(task), text)
    if llm_reply:
        return Reply(reply=llm_reply, state=task["state"] if task else "idle",
                     task=_task_view(task) if task else None, buttons=_buttons_for(task))
    if task:
        return Reply(reply=persona.remind_step(_current_step_text(task)),
                     state=task["state"], task=_task_view(task), buttons=_buttons_for(task))
    return Reply(reply=persona.idle_reply(), state="idle")


# ---------- 任务流程 ----------

def _create_task(user_id: str, text: str) -> Reply:
    title = _extract_title(text)
    domain = domain_of(title)
    emotion = llm.detect_emotion(text)

    # 摩擦地图：该领域的默认粒度作为起点
    friction = db.get_friction(user_id, domain)
    level = friction["default_level"]
    if emotion in ("焦虑", "低落"):
        level = max(1, level - 1)
    elif emotion == "亢奋":
        level = min(3, level + 1)

    decomposed = llm.decompose(title)
    levels_json = json.dumps(decomposed, ensure_ascii=False)
    db.create_active_task(user_id, title, levels_json, level, state="ready")
    task = db.get_active_task(user_id)

    reply = persona.task_ready(title, domain)
    if friction["default_level"] <= 1:
        reply = persona.friction_note() + " " + reply
    reply = f"{reply} {persona.ask_when()}"
    return Reply(reply=reply, state="ready", task=_task_view(task),
                 buttons=["现在开始", "待会儿", "今天不做"])


def handle_choose_time(user_id: str, when: str) -> Reply:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")
    if when == "now":
        db.update_active_task(user_id, state="committing")
        task = db.get_active_task(user_id)
        return Reply(reply=persona.commit_prompt(), state="committing", task=_task_view(task),
                     buttons=["行", "再想想"])
    if when == "later":
        due = (datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds")
        db.add_reminder(user_id, f"该开始「{task['title']}」啦", due)
        return Reply(reply=persona.scheduled("半小时后"), state="ready", task=_task_view(task), buttons=[])
    # not_today
    db.clear_active_task(user_id)
    return Reply(reply=persona.rest_day(), state="idle")


def handle_commit(user_id: str, agree: bool) -> Reply:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")
    if agree:
        db.update_active_task(user_id, state="executing")
        step = _current_step_text(task)
        return Reply(reply=f"{persona.commit_agree()} 「{step}」", state="executing",
                     task=_task_view(db.get_active_task(user_id)),
                     buttons=["完成这一步", "太重了", "今天到这吧"])
    db.update_active_task(user_id, state="ready")
    return Reply(reply=persona.commit_disagree(), state="ready", task=_task_view(task),
                 buttons=["现在开始", "待会儿", "今天不做"])


def handle_step_complete(user_id: str, duration_ms: int) -> Reply:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")

    direction = judge(duration_ms)
    domain = domain_of(task["title"])
    if direction == "up":
        db.record_friction(user_id, domain, "smooth")
    elif direction == "down":
        db.record_friction(user_id, domain, "stuck")

    steps_done = task["steps_done"] + 1
    db.record_step_done(user_id, task["title"])
    db.update_active_task(user_id, steps_done=steps_done)

    levels = _levels_of(task)
    cur_total = len(levels.get(level_name(task["level"]), []))
    new_level = task["level"] if direction == "keep" else shift_level(task["level"], direction)
    new_total = len(levels.get(level_name(new_level), []))

    if task["current_idx"] + 1 >= cur_total:
        return _complete(user_id, task, steps_done)

    next_idx = map_progress(task["current_idx"] + 1, cur_total, new_total)
    db.update_active_task(user_id, level=new_level, current_idx=next_idx, state="executing")
    task2 = db.get_active_task(user_id)
    step = _current_step_text(task2)

    if direction == "up":
        reply = f"{persona.step_next_aside('up')} 下一步：「{step}」"
    elif direction == "down":
        reply = f"{persona.step_next_aside('down')} 下一步：「{step}」"
    else:
        reply = f"好。下一步：「{step}」"

    notes = db.get_pending_notes(user_id)
    if notes:
        db.mark_notes_recalled(user_id)
        reply = f"{persona.note_recall(notes)} {reply}"

    return Reply(reply=reply, state="executing", task=_task_view(task2),
                 buttons=["完成这一步", "太重了", "今天到这吧"])


def _complete(user_id: str, task: dict, steps_done: int) -> Reply:
    db.clear_active_task(user_id)
    summary = db.get_today_summary(user_id)
    return Reply(reply=persona.all_done(task["title"], steps_done), state="done",
                 summary=_summary_text(summary), buttons=[])


def handle_resize(user_id: str, direction: str) -> Reply:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")

    gdir = "down" if direction == "smaller" else "up"
    domain = domain_of(task["title"])
    db.record_friction(user_id, domain, "stuck" if direction == "smaller" else "smooth")

    levels = _levels_of(task)
    cur_total = len(levels.get(level_name(task["level"]), []))
    new_level = shift_level(task["level"], gdir)
    new_total = len(levels.get(level_name(new_level), []))

    if new_level == task["level"]:
        return Reply(reply=persona.boundary(gdir), state="executing", task=_task_view(task),
                     buttons=["完成这一步", "太重了", "今天到这吧"])

    new_idx = map_progress(task["current_idx"], cur_total, new_total)
    db.update_active_task(user_id, level=new_level, current_idx=new_idx)
    task2 = db.get_active_task(user_id)
    step = _current_step_text(task2)
    reply = f"{persona.shrink() if direction == 'smaller' else persona.grow()} 现在这一步：「{step}」"
    return Reply(reply=reply, state="executing", task=_task_view(task2),
                 buttons=["完成这一步", "太重了", "今天到这吧"])


def _gentle_end(user_id: str, task: dict) -> Reply:
    db.clear_active_task(user_id)
    summary = db.get_today_summary(user_id)
    if summary["titles"]:
        what = "动了「" + "」「".join(summary["titles"]) + "」"
        reply = persona.gentle_end(what)
    else:
        reply = persona.gentle_end("来了")
    return Reply(reply=reply, state="idle", summary=_summary_text(summary))


def handle_exit(user_id: str, gentle: bool = False) -> Reply:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        summary = db.get_today_summary(user_id)
        return Reply(reply=persona.exit_line(), state="idle", summary=_summary_text(summary))
    return _gentle_end(user_id, task)


# ---------- 便签 / 发呆 / 休息 / 换事 ----------

def handle_note(user_id: str, content: str) -> Reply:
    db.ensure_user(user_id)
    db.add_note(user_id, content)
    return _note_reply(user_id)


def _note_reply(user_id: str) -> Reply:
    task = db.get_active_task(user_id)
    return Reply(reply=persona.note_ok(), state=task["state"] if task else "idle",
                 task=_task_view(task) if task else None, buttons=_buttons_for(task))


def _note(user_id: str, text: str) -> Reply:
    content = text
    for w in _NOTE:
        if w in text:
            content = text.split(w, 1)[-1].strip("，。！？、,.!? ")
            break
    db.add_note(user_id, content or text)
    return _note_reply(user_id)


def _afk(user_id: str) -> Reply:
    task = db.get_active_task(user_id)
    return Reply(reply=persona.afk_ok(), state=task["state"] if task else "idle",
                 task=_task_view(task) if task else None, buttons=_buttons_for(task))


def _rest_day(user_id: str) -> Reply:
    db.clear_active_task(user_id)
    return Reply(reply=persona.rest_day(), state="idle")


def _switch_task(user_id: str, text: str) -> Reply:
    old = db.get_active_task(user_id)
    new_title = _extract_title(text)
    if old:
        db.clear_active_task(user_id)
    if new_title == "这件事":
        return Reply(reply=persona.switch_ask(), state="idle")
    return _create_task(user_id, text)


# ---------- 跨天交接 ----------

def resume_handoff(user_id: str) -> Reply:
    handoff = db.get_handoff(user_id)
    if not handoff:
        return Reply(reply=persona.handoff_dismiss(), state="idle")
    db.create_active_task(user_id, handoff["title"], handoff["levels_json"], handoff["level"],
                          current_idx=handoff["current_idx"], steps_done=handoff["steps_done"],
                          state=handoff["state"] or "executing")
    db.clear_handoff(user_id)
    task = db.get_active_task(user_id)
    step = _current_step_text(task)
    return Reply(reply=persona.handoff_resume(step), state="executing", task=_task_view(task),
                 buttons=["完成这一步", "太重了", "今天到这吧"])


def dismiss_handoff(user_id: str) -> Reply:
    db.clear_handoff(user_id)
    return Reply(reply=persona.handoff_dismiss(), state="idle")


# ---------- 查询 ----------

def get_state(user_id: str) -> dict:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        return {"state": "idle", "task": None}
    return {"state": task["state"], "task": _task_view(task).model_dump()}


def get_history(user_id: str) -> list[dict]:
    db.ensure_user(user_id)
    return db.get_day_logs(user_id)


def get_daily_summary(user_id: str) -> dict:
    db.ensure_user(user_id)
    return db.get_today_summary(user_id)
