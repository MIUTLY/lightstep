"""SQLite 存储层（stdlib sqlite3，无 ORM 依赖）。

三层记忆模型：
  - 任务级（active_task / day_log）：跨天保留
  - 偏好级（preferences / friction / handoff）：长期沉淀，跨天保留
  - 便签（notes）；历史提醒表只保留兼容数据，不创建或投递提醒；回执与私人手帐仅存客户端
"""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime

from .config import settings
from .decompose import domain_of

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memo_state(user_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memo_operations(user_id TEXT, request_id TEXT, payload TEXT NOT NULL,
    attempt TEXT NOT NULL, response TEXT, PRIMARY KEY(user_id,request_id));

CREATE TABLE IF NOT EXISTS task_generation_drafts (
    user_id TEXT PRIMARY KEY,
    draft_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    first_seen     TEXT,
    last_seen      TEXT,
    open_count     INTEGER NOT NULL DEFAULT 0,
    same_day_opens INTEGER NOT NULL DEFAULT 0,
    visit_dates    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS preferences (
    user_id             TEXT PRIMARY KEY,
    default_granularity INTEGER NOT NULL DEFAULT 2,
    too_big_count       INTEGER NOT NULL DEFAULT 0,
    too_easy_count      INTEGER NOT NULL DEFAULT 0,
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS active_task (
    user_id     TEXT PRIMARY KEY,
    title       TEXT,
    levels_json TEXT,
    level       INTEGER,
    current_idx INTEGER,
    steps_done  INTEGER,
    state       TEXT,
    date        TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS day_log (
    user_id     TEXT,
    date        TEXT,
    title       TEXT,
    steps_done  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, date, title)
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    content    TEXT,
    recalled   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    label      TEXT,
    due_at     TEXT,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT
);

-- 当前任务的开始预约，独立于通用便签提醒；每人至多一项。
CREATE TABLE IF NOT EXISTS task_start_reminders (
    user_id    TEXT PRIMARY KEY,
    due_at     TEXT NOT NULL,
    notified   INTEGER NOT NULL DEFAULT 0
);

-- 摩擦地图：按领域沉淀"哪里容易卡"（长期，跨天保留）
CREATE TABLE IF NOT EXISTS friction (
    user_id       TEXT,
    domain        TEXT,
    stuck         INTEGER NOT NULL DEFAULT 0,
    smooth        INTEGER NOT NULL DEFAULT 0,
    default_level INTEGER NOT NULL DEFAULT 2,
    updated_at    TEXT,
    PRIMARY KEY (user_id, domain)
);

-- 跨天温柔交接：任务做了一半没关时，"上次写到哪"的残留（被消费后清除）
CREATE TABLE IF NOT EXISTS handoff (
    user_id     TEXT PRIMARY KEY,
    title       TEXT,
    levels_json TEXT,
    level       INTEGER,
    current_idx INTEGER,
    steps_done  INTEGER,
    state       TEXT,
    saved_date  TEXT,
    updated_at  TEXT
);

"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")



class DB:
    def __init__(self, path: str | None = None):
        self.path = path or settings.db_path
        self._init()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self):
        with self._conn() as c:
            c.executescript(_SCHEMA)

    # ---------- 用户 ----------

    def get_or_create_user(self, user_id: str) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row)

    def _rollover(self, user_id: str) -> bool:
        """仅判断日期变化，不清理任务、进度或完成记录。"""
        user = self.get_or_create_user(user_id)
        today = today_str()
        if not user["last_seen"] or user["last_seen"] == today:
            return False
        return True

    def ensure_user(self, user_id: str) -> dict:
        """确保用户存在并更新访问日期，但不增加 open_count（聊天不应算一次打开）。"""
        self._rollover(user_id)
        with self._conn() as c:
            c.execute("UPDATE users SET last_seen=? WHERE user_id=?", (today_str(), user_id))
        return self.get_or_create_user(user_id)

    def open_session(self, user_id: str) -> dict:
        user = self.get_or_create_user(user_id)
        new_day = self._rollover(user_id)
        today = today_str()
        same_day_opens = 1 if new_day else user["same_day_opens"] + 1
        visit_dates = json.loads(user["visit_dates"] or "[]")
        if today not in visit_dates:
            visit_dates.append(today)
        first_seen = user["first_seen"] or today
        open_count = user["open_count"] + 1
        with self._conn() as c:
            c.execute(
                "UPDATE users SET first_seen=?, last_seen=?, open_count=?, same_day_opens=?, visit_dates=? WHERE user_id=?",
                (first_seen, today, open_count, same_day_opens,
                 json.dumps(visit_dates, ensure_ascii=False), user_id),
            )
        return {
            "new_day": new_day,
            "open_count": open_count,
            "same_day_opens": same_day_opens,
            "first_open": user["first_seen"] is None,
            "visit_dates": visit_dates,
        }

    # ---------- 偏好 ----------

    def get_preferences(self, user_id: str) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                c.execute("INSERT INTO preferences (user_id) VALUES (?)", (user_id,))
                row = c.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,)).fetchone()
            return dict(row)

    def update_preferences(self, user_id: str, **fields) -> None:
        cols = [f"{k}=?" for k in fields]
        vals = list(fields.values()) + [now_iso(), user_id]
        with self._conn() as c:
            c.execute(f"UPDATE preferences SET {', '.join(cols)}, updated_at=? WHERE user_id=?", vals)

    # ---------- AI生成草稿：失败不修改当前任务 ----------

    def get_generation(self, user_id):
        with self._conn() as c:
            row = c.execute("SELECT draft_json FROM task_generation_drafts WHERE user_id=?", (user_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def begin_generation(self, user_id, original_input, goal, answers=None, previous_id=None):
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT draft_json FROM task_generation_drafts WHERE user_id=?", (user_id,)).fetchone()
            if previous_id is not None and (not row or json.loads(row[0])["generation_id"] != previous_id):
                return None
            task = c.execute("SELECT * FROM active_task WHERE user_id=?", (user_id,)).fetchone()
            draft = {"generation_id": uuid.uuid4().hex, "original_input": original_input, "goal": goal,
                     "answers": answers or [], "expected_task": dict(task) if task else None,
                     "status": "generating", "question": None, "error": None, "updated_at": now_iso()}
            c.execute("INSERT OR REPLACE INTO task_generation_drafts VALUES (?, ?)",
                      (user_id, json.dumps(draft, ensure_ascii=False)))
            return draft

    def finish_generation(self, user_id, generation_id, *, status, question=None, error=None):
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT draft_json FROM task_generation_drafts WHERE user_id=?", (user_id,)).fetchone()
            if not row:
                return False
            draft = json.loads(row[0])
            if draft["generation_id"] != generation_id or draft["status"] != "generating":
                return False
            draft.update(status=status, question=question, error=error, updated_at=now_iso())
            c.execute("UPDATE task_generation_drafts SET draft_json=? WHERE user_id=?",
                      (json.dumps(draft, ensure_ascii=False), user_id))
            return True

    def install_generated_task(self, user_id, draft, title, levels_json):
        """Atomically compare both draft and task snapshots before replacing anything."""
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            if self._memo_is_active(c, user_id):
                return False
            row = c.execute("SELECT draft_json FROM task_generation_drafts WHERE user_id=?", (user_id,)).fetchone()
            if not row or json.loads(row[0])["generation_id"] != draft["generation_id"] or json.loads(row[0])["status"] != "generating":
                return False
            task = c.execute("SELECT * FROM active_task WHERE user_id=?", (user_id,)).fetchone()
            if (dict(task) if task else None) != draft["expected_task"]:
                return False
            c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            c.execute("UPDATE users SET last_seen=? WHERE user_id=?", (today_str(), user_id))
            c.execute("INSERT OR REPLACE INTO active_task "
                      "(user_id,title,levels_json,level,current_idx,steps_done,state,date,updated_at) "
                      "VALUES (?,?,?,2,0,0,'ready',?,?)", (user_id, title, levels_json, today_str(), now_iso()))
            c.execute("DELETE FROM task_start_reminders WHERE user_id=?", (user_id,))
            saved = dict(draft, status="succeeded", question=None, error=None, updated_at=now_iso())
            c.execute("UPDATE task_generation_drafts SET draft_json=? WHERE user_id=?",
                      (json.dumps(saved, ensure_ascii=False), user_id))
            return True

    # ---------- 当前任务 ----------

    def _memo_is_active(self, c, user_id):
        row = c.execute('SELECT data FROM memo_state WHERE user_id=?', (user_id,)).fetchone()
        return bool(row and json.loads(row[0]).get('active'))

    def create_active_task(self, user_id: str, title: str, levels_json: str, level: int,
                           current_idx: int = 0, steps_done: int = 0, state: str = "ready") -> None:
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            if self._memo_is_active(c, user_id):
                from fastapi import HTTPException
                raise HTTPException(409, '请先结束备忘录专注。')
            c.execute(
                "INSERT OR REPLACE INTO active_task "
                "(user_id, title, levels_json, level, current_idx, steps_done, state, date, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, title, levels_json, level, current_idx, steps_done, state, today_str(), now_iso()),
            )
            c.execute("DELETE FROM task_start_reminders WHERE user_id=?", (user_id,))

    def get_active_task(self, user_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM active_task WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def update_active_task(self, user_id: str, **fields) -> None:
        cols = [f"{k}=?" for k in fields]
        vals = list(fields.values()) + [now_iso(), user_id]
        with self._conn() as c:
            c.execute(f"UPDATE active_task SET {', '.join(cols)}, updated_at=? WHERE user_id=?", vals)
            if "state" in fields and fields["state"] != "ready":
                c.execute("DELETE FROM task_start_reminders WHERE user_id=?", (user_id,))

    def clear_active_task(self, user_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM active_task WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM task_start_reminders WHERE user_id=?", (user_id,))

    def update_plan_if_current(self, task: dict, levels_json: str, level: int, current_idx: int,
                               *, completed: bool = False, finished: bool = False) -> bool:
        """新森林的进度与完成计数在同一事务提交；旧快照不能覆盖较新进度。"""
        fields = ("title", "levels_json", "level", "current_idx", "steps_done", "state", "date")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM active_task WHERE user_id=?", (task["user_id"],)).fetchone()
            if not row or any(row[key] != task[key] for key in fields):
                return False
            if completed:
                c.execute(
                    "INSERT INTO day_log (user_id, date, title, steps_done) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(user_id, date, title) DO UPDATE SET steps_done=steps_done+1",
                    (task["user_id"], today_str(), task["title"]))
            if finished:
                c.execute("DELETE FROM active_task WHERE user_id=?", (task["user_id"],))
                c.execute("DELETE FROM task_start_reminders WHERE user_id=?", (task["user_id"],))
            else:
                c.execute(
                    "UPDATE active_task SET levels_json=?, level=?, current_idx=?, steps_done=?, updated_at=? "
                    "WHERE user_id=?",
                    (levels_json, level, current_idx, task["steps_done"] + int(completed), now_iso(), task["user_id"]))
        return True

    # ---------- 当日记录 ----------

    def record_step_done(self, user_id: str, title: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO day_log (user_id, date, title, steps_done) VALUES (?, ?, ?, 1) "
                "ON CONFLICT(user_id, date, title) DO UPDATE SET steps_done=steps_done+1",
                (user_id, today_str(), title),
            )

    def get_day_logs(self, user_id: str, limit: int = 30) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT date, title FROM day_log WHERE user_id=? AND steps_done>0 "
                "ORDER BY date DESC LIMIT ?", (user_id, limit),
            ).fetchall()
        return [{"date": r["date"], "title": r["title"]} for r in rows]

    def get_today_summary(self, user_id: str) -> dict:
        today = today_str()
        with self._conn() as c:
            rows = c.execute(
                "SELECT title, steps_done FROM day_log WHERE user_id=? AND date=? AND steps_done>0",
                (user_id, today),
            ).fetchall()
        titles = [r["title"] for r in rows]
        steps = sum(r["steps_done"] for r in rows)
        return {"date": today, "steps_done": steps, "titles": titles}

    # ---------- 便签 / 提醒 ----------

    def add_note(self, user_id: str, content: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO notes (user_id, content, created_at) VALUES (?, ?, ?)",
                      (user_id, content, now_iso()))

    def get_pending_notes(self, user_id: str) -> list[str]:
        with self._conn() as c:
            rows = c.execute("SELECT content FROM notes WHERE user_id=? AND recalled=0 ORDER BY id",
                             (user_id,)).fetchall()
        return [r["content"] for r in rows]

    def mark_notes_recalled(self, user_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE notes SET recalled=1 WHERE user_id=? AND recalled=0", (user_id,))

    # ---------- 摩擦地图 ----------

    def get_friction(self, user_id: str, domain: str) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT * FROM friction WHERE user_id=? AND domain=?", (user_id, domain)).fetchone()
            if row is None:
                c.execute("INSERT INTO friction (user_id, domain) VALUES (?, ?)", (user_id, domain))
                row = c.execute("SELECT * FROM friction WHERE user_id=? AND domain=?", (user_id, domain)).fetchone()
            return dict(row)

    def record_friction(self, user_id: str, domain: str, signal: str) -> None:
        """signal: "stuck"（卡）| "smooth"（顺）。净差跨过阈值就调档并重置计数。"""
        f = self.get_friction(user_id, domain)
        stuck, smooth, level = f["stuck"], f["smooth"], f["default_level"]
        if signal == "stuck":
            stuck += 1
        else:
            smooth += 1
        if stuck - smooth >= 3 and level > 1:
            level -= 1
            stuck = smooth = 0
        elif smooth - stuck >= 3 and level < 3:
            level += 1
            stuck = smooth = 0
        with self._conn() as c:
            c.execute(
                "UPDATE friction SET stuck=?, smooth=?, default_level=?, updated_at=? WHERE user_id=? AND domain=?",
                (stuck, smooth, level, now_iso(), user_id, domain),
            )

    # ---------- 跨天交接 ----------

    def _save_handoff_from_task(self, user_id: str, task: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO handoff "
                "(user_id, title, levels_json, level, current_idx, steps_done, state, saved_date, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, task["title"], task["levels_json"], task["level"], task["current_idx"],
                 task["steps_done"], task["state"], task["date"], now_iso()),
            )

    def get_handoff(self, user_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM handoff WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def clear_handoff(self, user_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM handoff WHERE user_id=?", (user_id,))



db = DB()
