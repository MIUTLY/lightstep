"""核心编排：把所有接口串成一条温柔的任务流。

职责：
  - 意图识别（关键词规则，离线可用）
  - 状态机：idle → ready → committing → executing → done
  - 自适应粒度、摩擦地图、跨天交接、便签与提醒
  - 回执图片及回执留言由客户端保存，不写入服务端
"""
import json
from datetime import datetime, timedelta

from fastapi import HTTPException

from . import persona
from .db import db
from .decompose import domain_of
from .ending_intent import ending_intent
from .granularity import judge, shift_level, level_name
from . import step_plan, task_forest
from .llm import llm, AIError, Clarification, invalid_response
from .schemas import Reply, TaskView

# ---------- 意图关键词 ----------

_NEGATIVE = ["不想", "不要", "算了", "不用", "不做", "不做了"]
_GOAL_INTENT = ["想", "要", "得", "该", "准备", "打算", "试试", "试着", "今晚", "今晚要", "开始做"]
_GOAL_VERBS = ["刷题", "写", "背", "读", "看", "学", "复习", "整理", "收拾", "跑步", "健身",
               "运动", "练", "做题", "改", "画", "做", "洗", "打扫", "清洁"]
_TOO_BIG = ["太多", "太重", "太大", "好难", "太难", "做不完", "好多", "缩小", "拆细", "拆小", "太累", "有点难", "轻一点"]
_TOO_EASY = ["太简单", "太容易", "加量", "加一点", "不够", "太少", "放大", "太轻松", "重一点"]
_NOTE = ["记一下", "记个", "记得", "别忘", "提醒我", "备忘", "记下", "帮我记"]
_AFK = ["手机", "视频", "打游戏", "玩游戏", "抖音", "短视频", "刷", "走神", "发呆", "摸鱼", "躺一会儿"]
_REST = ["什么都不想干", "不想干", "今天休息", "放假", "躺平", "摆烂", "休息一天", "今天不想", "不干了"]
_SWITCH = ["换个任务", "换成", "改做", "不做这个", "换一个", "换件事", "换个事"]
_CONTINUE = ["接着", "继续"]
_START_BUTTONS = ["现在开始", "5分钟后", "10分钟后", "今天不做"]

_LEAD_FILLERS = sorted(
    ["那我试试", "我试试", "我试", "试试看", "试着", "我想", "我想做", "我要", "我准备", "我打算",
     "我们", "我们来", "今晚", "今天", "准备", "打算", "换个任务", "换件事", "换成", "改做",
     "好", "那", "就", "先", "去", "来", "吧"],
    key=len, reverse=True,
)


# ---------- 小工具 ----------

def _has_any(text: str, words) -> bool:
    return any(w in text for w in words)


def _is_question(text: str) -> bool:
    return _has_any(text, ("怎么", "怎样", "如何", "为什么", "什么", "是否", "能否", "能不能", "可不可以", "吗", "?", "？"))


def _command_text(text: str) -> str:
    command = text.strip()
    for prefix in ("我想", "我要", "请", "那就", "那"):
        if command.startswith(prefix):
            command = command[len(prefix):].lstrip("，, ")
    return command


def _is_switch_command(text: str) -> bool:
    # 换任务要有明确的命令开头；“换一个方法”不能误删任务。
    command = _command_text(text)
    if command.startswith(("换一个方法", "换一个说法", "换个方法", "换个说法")):
        return False
    return any(command.startswith(word) for word in _SWITCH)


def _require_task_state(user_id: str, allowed: tuple[str, ...]) -> dict | None:
    # 先只读校验，非法动作不创建用户、不清理任务、不改变偏好。
    task = db.get_active_task(user_id)
    if not task or task["state"] not in allowed:
        raise HTTPException(status_code=409, detail={
            "code": "INVALID_TASK_STATE",
            "message": "当前状态不能执行这个动作，请刷新任务后再试。",
        })
    # 合法动作仍沿用原有跨天处理；不在本轮重新定义数据保留规则。
    db.ensure_user(user_id)
    return db.get_active_task(user_id)


def _validate_choice(value, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise HTTPException(status_code=422, detail={
            "code": "INVALID_TASK_PARAMETER", "message": "任务操作参数无效。",
        })


def _levels_of(task: dict) -> dict:
    return json.loads(task["levels_json"])


def _forest_plan(task: dict) -> dict | None:
    if not task_forest.is_forest(_levels_of(task)):
        return None
    try:
        return task_forest.read(task)
    except (ValueError, KeyError, TypeError, RecursionError) as error:
        raise HTTPException(status_code=409, detail={
            "code": "INVALID_TASK_PLAN", "message": "任务结构暂时无法读取，进度已保留。"}) from error


def _current_step_text(task: dict) -> str:
    plan = _forest_plan(task)
    return task_forest.view(plan)["current_step"] if plan is not None else step_plan.current_text(task)


def _task_view(task: dict) -> TaskView:
    plan = _forest_plan(task)
    extra = task_forest.view(plan) if plan is not None else {
        "current_step": step_plan.current_text(task), "step_id": step_plan.step_id(task)}
    return TaskView(
        title=task["title"],
        steps_done=task["steps_done"],
        granularity=level_name(task["level"]),
        state=task["state"],
        plan_format="forest_v1" if plan is not None else "legacy",
        **extra,
        start_due_at=db.get_start_due_at(task["user_id"]) if task["state"] == "ready" else None,
    )


def _buttons_for(task) -> list[str]:
    if not task:
        return []
    if task["state"] == "executing" and task_forest.is_forest(_levels_of(task)):
        return ["轻一点", "完成这一步", "重一点", "今天到这吧"]
    return {
        "ready": _START_BUTTONS,
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
    return _current_step_text(handoff)


# ---------- 会话 ----------

def handle_open(user_id: str) -> Reply:
    result = _handle_open(user_id)
    result.generation = generation_status(user_id)
    return result


def _handle_open(user_id: str) -> Reply:
    info = db.open_session(user_id)
    task = db.get_active_task(user_id)
    due = db.due_reminders(user_id) + db.take_due_start_reminder(user_id)

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
    # Generation must run before rollover: a failed replacement cannot clear yesterday's task.
    task = db.get_active_task(user_id)
    draft = db.get_generation(user_id)
    if draft and draft["status"] == "needs_clarification" and text.startswith(("补充：", "补充:")):
        answer = text[3:].strip()
        if not answer:
            return _generation_reply(user_id, "请在“补充：”后写下答案。")
        return retry_generation(user_id, draft["generation_id"], answer)
    if text in ("重试", "重试生成") and draft and draft["status"] in ("failed", "generating"):
        return retry_generation(user_id, draft["generation_id"])
    if text and _is_switch_command(text) and not _is_question(text) and not _has_any(text, _NOTE) and not ending_intent(text):
        return _switch_task(user_id, text)
    if text and not task and _is_goal(text) and not _has_any(text, _NOTE + _REST + _AFK) and not ending_intent(text):
        return _create_task(user_id, text)
    # Clarification answers use a distinct endpoint; never steal task commands or ordinary questions.
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not text:
        return Reply(reply=persona.afk_due(), state=task["state"] if task else "idle",
                     task=_task_view(task) if task else None, buttons=_buttons_for(task))
    return _chat_reply(user_id, text)


def poll_start_reminder(user_id: str) -> Reply:
    db.ensure_user(user_id)
    due = db.take_due_start_reminder(user_id)
    task = db.get_active_task(user_id)
    return Reply(reply="", state=task["state"] if task else "idle",
                 task=_task_view(task) if task else None, buttons=_buttons_for(task), due_reminders=due)


def _chat_reply(user_id: str, text: str) -> Reply:
    task = db.get_active_task(user_id)

    # 先识别完整的收尾表达；“结束条件是什么”“不要结束”不能清空任务。
    ending = ending_intent(text)
    if ending == "end":
        return _gentle_end(user_id, task) if task else Reply(reply=persona.exit_line(), state="idle")
    if ending == "tired":
        if not task:
            return Reply(reply=persona.tired_idle(), state="idle")
        return Reply(reply=persona.tired_choice(), state=task["state"], task=_task_view(task),
                     buttons=["今天到这吧", "太重了"])

    resize_request = _has_any(text, ("帮我拆小", "帮我拆细", "能拆小", "能拆细", "可以拆小",
                                    "可以拆细", "能不能拆小", "能不能拆细", "帮我加量",
                                    "能轻一点", "可以轻一点", "帮我轻一点", "能重一点", "可以重一点", "帮我重一点"))
    if task and _is_question(text) and not resize_request:
        return _answer_current_step(task, text)

    # 1. 接着上次（跨天交接）
    if not task and _has_any(text, _CONTINUE) and db.get_handoff(user_id):
        return resume_handoff(user_id)

    # 3. 走神记笔记
    if _has_any(text, _NOTE):
        return _note(user_id, text)

    # 4. 今天什么都不想干
    if not task and _has_any(text, _REST):
        return _rest_day(user_id)

    # 5. 换件事
    if _is_switch_command(text):
        return _switch_task(user_id, text)

    # 6. 太重 / 太简单（有任务时）
    if task and _has_any(text, _TOO_BIG):
        return handle_resize(user_id, "smaller")
    if task and _has_any(text, _TOO_EASY):
        return handle_resize(user_id, "bigger")

    # 7. 想做事（新任务 / 替换当前）
    if not task and _is_goal(text):
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


def _answer_current_step(task: dict, text: str) -> Reply:
    answer = llm.reply(_describe_state(task), text)
    return Reply(reply=answer or persona.remind_step(_current_step_text(task)),
                 state=task["state"], task=_task_view(task), buttons=_buttons_for(task))


# ---------- 任务流程 ----------

def generation_status(user_id: str):
    draft = db.get_generation(user_id)
    if draft is None:
        return None
    return {k: v for k, v in draft.items() if k != "expected_task"}


def _generation_reply(user_id, message):
    task = db.get_active_task(user_id)
    generation = generation_status(user_id)
    buttons = _buttons_for(task)
    if generation and generation["status"] == "failed":
        buttons = ["重试生成"] + buttons
    return Reply(reply=message, state=task["state"] if task else "idle",
                 task=_task_view(task) if task else None, buttons=buttons, generation=generation)


def _run_generation(user_id, draft):
    try:
        # Pass the original goal, not the domain or a title with meaningful words removed.
        goal = draft["goal"]
        if draft["answers"]:
            goal = json.dumps({"original_goal": goal, "clarification_answers": draft["answers"]}, ensure_ascii=False)
        decomposed = llm.decompose(goal)
        try:
            levels = task_forest.new_plan(decomposed)
        except (ValueError, TypeError, KeyError, RecursionError):
            raise invalid_response() from None
        if not db.install_generated_task(user_id, draft, draft["goal"], json.dumps(levels, ensure_ascii=False)):
            raise AIError("TASK_CHANGED", "生成期间任务或目标已变化，已有进度已保留，请重试生成。", 409)
    except Clarification as clarify:
        if not db.finish_generation(user_id, draft["generation_id"], status="needs_clarification", question=clarify.question):
            raise HTTPException(409, "目标已变化，请刷新后再试。")
        return _generation_reply(user_id, clarify.question + " 请回复“补充：你的答案”。")
    except AIError as error:
        if not db.finish_generation(user_id, draft["generation_id"], status="failed",
                error={"code": error.code, "message": error.message, "retryable": True}):
            raise HTTPException(409, "目标已变化，旧生成结果未保存，请刷新后再试。")
        return _generation_reply(user_id, error.message + " 原始输入已保留，已有任务和进度不会因此改变。")
    return _generation_reply(user_id, "任务已准备好，只展示当前这一段。 " + persona.ask_when())


def _create_task(user_id: str, text: str, *, original_input=None) -> Reply:
    draft = db.begin_generation(user_id, text if original_input is None else original_input, text)
    return _run_generation(user_id, draft)


def retry_generation(user_id, generation_id, answer=None):
    previous = db.get_generation(user_id)
    if not previous or previous["generation_id"] != generation_id or previous["status"] == "succeeded":
        raise HTTPException(409, "生成请求已变化或已成功，请刷新后再试。")
    if answer is not None and previous["status"] != "needs_clarification":
        raise HTTPException(409, "当前没有需要回答的澄清问题。")
    if answer is None and previous["status"] == "needs_clarification":
        raise HTTPException(409, "请先回答澄清问题，再生成任务。")
    answers = previous["answers"] + ([{"question": previous["question"], "answer": answer}] if answer else [])
    draft = db.begin_generation(user_id, previous["original_input"], previous["goal"], answers, previous_id=generation_id)
    if draft is None:
        raise HTTPException(409, "生成请求已变化，请刷新后再试。")
    return _run_generation(user_id, draft)


def handle_choose_time(user_id: str, when: str) -> Reply:
    _validate_choice(when, ("now", "in_5_minutes", "in_10_minutes", "later", "not_today"))
    task = _require_task_state(user_id, ("ready",))
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")
    if when == "now":
        db.update_active_task(user_id, state="committing")
        task = db.get_active_task(user_id)
        return Reply(reply=persona.commit_prompt(), state="committing", task=_task_view(task),
                     buttons=["行", "再想想"])
    if when == "later":
        return Reply(reply=persona.ask_delay(), state="ready", task=_task_view(task), buttons=_START_BUTTONS)
    if when in ("in_5_minutes", "in_10_minutes"):
        minutes = 5 if when == "in_5_minutes" else 10
        if not db.schedule_task_start(user_id, minutes):
            raise HTTPException(status_code=409, detail={"code": "INVALID_TASK_STATE", "message": "任务已变化，请刷新后再选时间。"})
        return Reply(reply=persona.scheduled(f"{minutes}分钟后"), state="ready",
                     task=_task_view(db.get_active_task(user_id)), buttons=_START_BUTTONS)
    # not_today
    db.clear_active_task(user_id)
    return Reply(reply=persona.rest_day(), state="idle")


def handle_commit(user_id: str, agree: bool) -> Reply:
    if not isinstance(agree, bool):
        raise HTTPException(status_code=422, detail="agree必须为布尔值。")
    task = _require_task_state(user_id, ("committing",))
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")
    if agree:
        db.update_active_task(user_id, state="executing")
        step = _current_step_text(task)
        return Reply(reply=f"{persona.commit_agree()} 「{step}」", state="executing",
                     task=_task_view(db.get_active_task(user_id)),
                     buttons=_buttons_for(db.get_active_task(user_id)))
    db.update_active_task(user_id, state="ready")
    return Reply(reply=persona.commit_disagree(), state="ready", task=_task_view(db.get_active_task(user_id)),
                 buttons=_START_BUTTONS)


def handle_step_complete(user_id: str, duration_ms: int, step_id: str | None = None) -> Reply:
    if type(duration_ms) is not int or duration_ms < 0:
        raise HTTPException(status_code=422, detail="duration_ms必须为非负整数。")
    task = _require_task_state(user_id, ("executing",))
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")

    _validate_step_id(task, step_id)
    plan = _forest_plan(task)
    if plan is not None:
        return _complete_forest_step(user_id, task, plan, duration_ms)

    direction = judge(duration_ms)
    domain = domain_of(task["title"])
    if direction == "up":
        db.record_friction(user_id, domain, "smooth")
    elif direction == "down":
        db.record_friction(user_id, domain, "stuck")

    steps_done = task["steps_done"] + 1
    db.record_step_done(user_id, task["title"])
    db.update_active_task(user_id, steps_done=steps_done)

    levels = step_plan.ensure_plan(task)
    new_level = task["level"] if direction == "keep" else shift_level(task["level"], direction)
    next_idx = step_plan.next_cursor(levels, task["current_idx"])
    if step_plan.is_finished(levels, next_idx):
        return _complete(user_id, task, steps_done)
    step_plan.prepare_step(levels, next_idx, new_level)
    db.update_active_task(user_id, level=new_level, current_idx=next_idx, state="executing",
                          levels_json=json.dumps(levels, ensure_ascii=False))
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


def handle_resize(user_id: str, direction: str, step_id: str | None = None) -> Reply:
    _validate_choice(direction, ("smaller", "bigger"))
    task = _require_task_state(user_id, ("ready", "committing", "executing"))
    if not task:
        return Reply(reply=persona.afk_due(), state="idle")

    _validate_step_id(task, step_id)
    plan = _forest_plan(task)
    if plan is not None:
        return _resize_forest(user_id, task, plan, direction)

    gdir = "down" if direction == "smaller" else "up"
    domain = domain_of(task["title"])
    db.record_friction(user_id, domain, "stuck" if direction == "smaller" else "smooth")

    levels = step_plan.ensure_plan(task)
    new_level = shift_level(task["level"], gdir)
    before = _current_step_text(task)
    step_plan.prepare_step(levels, task["current_idx"], new_level)
    updated = dict(task, level=new_level, levels_json=json.dumps(levels, ensure_ascii=False))
    if new_level == task["level"] and _current_step_text(updated) == before:
        return Reply(reply=persona.boundary(gdir), state=task["state"], task=_task_view(task),
                     buttons=_buttons_for(task))
    db.update_active_task(user_id, level=new_level, levels_json=updated["levels_json"])
    task2 = db.get_active_task(user_id)
    step = _current_step_text(task2)
    if step == before:
        reply = persona.boundary(gdir)
    else:
        reply = f"{persona.shrink() if direction == 'smaller' else persona.grow()} 现在这一步：「{step}」"
    return Reply(reply=reply, state=task2["state"], task=_task_view(task2),
                 buttons=_buttons_for(task2))


def _validate_step_id(task: dict, expected: str | None) -> None:
    if expected is not None and expected != _task_view(task).step_id:
        raise HTTPException(status_code=409, detail={
            "code": "STALE_TASK_STEP", "message": "当前步骤已经变化，请刷新后再操作。"})


def _save_forest(task: dict, plan: dict, *, completed=False, finished=False) -> dict:
    level = task["level"] if finished else plan["nodes"][plan["current_node_id"]]["level"]
    levels_json = json.dumps({task_forest.KEY: plan}, ensure_ascii=False)
    index = task_forest.cursor(plan)
    if not db.update_plan_if_current(task, levels_json, level, index, completed=completed, finished=finished):
        raise HTTPException(status_code=409, detail={
            "code": "STALE_TASK_STEP", "message": "任务已变化，已完成部分已保留，请刷新。"})
    return dict(task, levels_json=levels_json, level=level, current_idx=index,
                steps_done=task["steps_done"] + int(completed))


def _complete_forest_step(user_id: str, task: dict, plan: dict, duration_ms: int) -> Reply:
    finished = task_forest.complete(plan)
    updated = _save_forest(task, plan, completed=True, finished=finished)
    # 耗时仍可沉淀摩擦反馈，但不覆盖主动选择或默认中档，也不切到独立清单。
    direction = judge(duration_ms)
    if direction != "keep":
        db.record_friction(user_id, domain_of(task["title"]), "smooth" if direction == "up" else "stuck")
    if finished:
        return Reply(reply="这次拆出的步骤做完了。先到这。", state="done",
                     summary=_summary_text(db.get_today_summary(user_id)))
    reply = f"好。下一步：「{_current_step_text(updated)}」"
    notes = db.get_pending_notes(user_id)
    if notes:
        db.mark_notes_recalled(user_id)
        reply = f"{persona.note_recall(notes)} {reply}"
    return Reply(reply=reply, state=updated["state"], task=_task_view(updated), buttons=_buttons_for(updated))


def _resize_forest(user_id: str, task: dict, plan: dict, direction: str) -> Reply:
    if not task_forest.resize(plan, direction):
        return Reply(reply=persona.boundary("down" if direction == "smaller" else "up"),
                     state=task["state"], task=_task_view(task), buttons=_buttons_for(task))
    updated = _save_forest(task, plan)
    db.record_friction(user_id, domain_of(task["title"]), "stuck" if direction == "smaller" else "smooth")
    return Reply(reply=f"现在这一步：「{_current_step_text(updated)}」", state=updated["state"],
                 task=_task_view(updated), buttons=_buttons_for(updated))


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
    command = _command_text(text)
    for word in sorted(_SWITCH, key=len, reverse=True):
        if command.startswith(word):
            command = command[len(word):]
            break
    new_title = command.strip("，。！？、,.!? ")
    if not new_title:
        return Reply(reply=persona.switch_ask(), state=old["state"] if old else "idle",
                     task=_task_view(old) if old else None, buttons=_buttons_for(old))
    # 新任务成功生成后再替换，不能在模型调用之前先删除旧任务。
    return _create_task(user_id, new_title, original_input=text)


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
                 buttons=_buttons_for(task))


def dismiss_handoff(user_id: str) -> Reply:
    db.clear_handoff(user_id)
    return Reply(reply=persona.handoff_dismiss(), state="idle")


# ---------- 查询 ----------

def get_state(user_id: str) -> dict:
    db.ensure_user(user_id)
    task = db.get_active_task(user_id)
    if not task:
        return {"state": "idle", "task": None, "generation": generation_status(user_id)}
    return {"state": task["state"], "task": _task_view(task).model_dump(), "generation": generation_status(user_id)}


def get_history(user_id: str) -> list[dict]:
    db.ensure_user(user_id)
    return db.get_day_logs(user_id)


def get_daily_summary(user_id: str) -> dict:
    db.ensure_user(user_id)
    return db.get_today_summary(user_id)
