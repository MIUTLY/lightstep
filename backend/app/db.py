"""SQLite 存储层（stdlib sqlite3，无 ORM 依赖）。

三层记忆模型：
  - 任务级（active_task / day_log）：当天清空
  - 偏好级（preferences / friction / handoff）：长期沉淀，跨天保留
  - 便签与提醒（notes / reminders）；回执与私人手帐仅存客户端
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .config import settings
from .decompose import domain_of

_SCHEMA = """
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        """跨天：先把"上次写到哪"存成交接，再清掉当天任务。返回是否跨天。"""
        user = self.get_or_create_user(user_id)
        today = today_str()
        if not user["last_seen"] or user["last_seen"] == today:
            return False
        task = self.get_active_task(user_id)
        if task and task["steps_done"] > 0:
            self._save_handoff_from_task(user_id, task)
        self.clear_active_task(user_id)
        return True

    def ensure_user(self, user_id: str) -> dict:
        """确保用户存在 + 做跨天清理，但不增加 open_count（聊天不应算一次打开）。"""
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

    # ---------- 当前任务 ----------

    def create_active_task(self, user_id: str, title: str, levels_json: str, level: int,
                           current_idx: int = 0, steps_done: int = 0, state: str = "ready") -> None:
        with self._conn() as c:
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

    def schedule_task_start(self, user_id: str, minutes: int) -> bool:
        if minutes not in (5, 10):
            raise ValueError("start delay must be 5 or 10 minutes")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            task = c.execute("SELECT state FROM active_task WHERE user_id=?", (user_id,)).fetchone()
            if not task or task["state"] != "ready":
                return False
            due = (utc_now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
            c.execute(
                "INSERT INTO task_start_reminders (user_id, due_at, notified) VALUES (?, ?, 0) "
                "ON CONFLICT(user_id) DO UPDATE SET due_at=excluded.due_at, notified=0", (user_id, due))
        return True

    def get_start_due_at(self, user_id: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT due_at FROM task_start_reminders WHERE user_id=?", (user_id,)).fetchone()
        return row["due_at"] if row else None

    def take_due_start_reminder(self, user_id: str) -> list[str]:
        # 取出并标记在同一事务，避免并行打开/轮询重复返回同一预约。
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT t.title FROM task_start_reminders r JOIN active_task t ON t.user_id=r.user_id "
                "WHERE r.user_id=? AND r.notified=0 AND r.due_at<=? AND t.state='ready'",
                (user_id, utc_now().isoformat(timespec="seconds")),
            ).fetchone()
            if not row:
                return []
            c.execute("UPDATE task_start_reminders SET notified=1 WHERE user_id=?", (user_id,))
        return [f"之前约好开始「{row['title']}」。想开始时点「现在开始」，不急。"]

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

    def add_reminder(self, user_id: str, label: str, due_at: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO reminders (user_id, label, due_at, created_at) VALUES (?, ?, ?, ?)",
                      (user_id, label, due_at, now_iso()))

    def due_reminders(self, user_id: str) -> list[str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT label FROM reminders WHERE user_id=? AND done=0 AND due_at<=? "
                "AND label NOT LIKE '该开始「%」啦' ORDER BY due_at",
                (user_id, now_iso()),
            ).fetchall()
        return [r["label"] for r in rows]

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
