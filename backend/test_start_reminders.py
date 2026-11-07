"""预约开始的HTTP、持久化、生命周期与并发取出回归。"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-schedule-boot-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "openai"

from fastapi.testclient import TestClient
from app.db import DB
from tests.fakes import MockLLM
from app.main import app


class StartReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lightstep-schedule-")
        self.db = DB(str(Path(self.tmp.name) / "test.db"))
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.db_patch = patch("app.services.db", self.db)
        self.llm_patch = patch("app.services.llm", MockLLM())
        self.clock_patch = patch("app.db.utc_now", side_effect=lambda: self.now)
        self.db_patch.start()
        self.llm_patch.start()
        self.clock_patch.start()
        self.client = TestClient(app)
        self.uid = "schedule-user"

    def tearDown(self):
        self.client.close()
        self.clock_patch.stop()
        self.llm_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def post(self, path, **payload):
        response = self.client.post(path, json={"user_id": self.uid, **payload})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def start(self):
        return self.post("/api/chat", message="换成背单词")

    def schedule(self, minutes=5):
        return self.post("/api/task/choose_time", when=f"in_{minutes}_minutes")

    def poll(self):
        return self.post("/api/reminders/poll")

    def rows(self):
        with self.db._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM task_start_reminders")]

    def snapshot(self):
        with self.db._conn() as c:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(r) for r in c.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
                    for name in tables}

    def test_five_and_ten_minutes_are_exact_and_do_not_start_or_advance(self):
        for minutes in (5, 10):
            self.start()
            task = self.db.get_active_task(self.uid)
            result = self.schedule(minutes)
            self.assertEqual(result["state"], "ready")
            self.assertEqual(result["task"]["steps_done"], 0)
            self.assertEqual(datetime.fromisoformat(result["task"]["start_due_at"]), self.now + timedelta(minutes=minutes))
            self.assertEqual(self.db.get_active_task(self.uid), task)
            state = self.client.get("/api/session/state", params={"user_id": self.uid}).json()
            self.assertEqual(state["task"], result["task"])
            self.assertIn("5分钟后", result["buttons"])
            self.assertIn("10分钟后", result["buttons"])

    def test_old_later_asks_for_duration_without_writing_a_schedule(self):
        self.start()
        before = self.snapshot()
        result = self.post("/api/task/choose_time", when="later")
        self.assertEqual(result["state"], "ready")
        self.assertIsNone(result["task"]["start_due_at"])
        self.assertEqual(self.snapshot(), before)

    def test_due_reminder_is_returned_once_without_auto_start(self):
        self.start()
        self.schedule()
        self.now += timedelta(minutes=5, seconds=-1)
        self.assertEqual(self.poll()["due_reminders"], [])
        self.now += timedelta(seconds=1)
        due = self.poll()
        self.assertEqual(len(due["due_reminders"]), 1)
        self.assertEqual(due["state"], "ready")
        self.assertEqual(due["task"]["steps_done"], 0)
        self.assertEqual(self.poll()["due_reminders"], [])
        self.assertEqual(self.post("/api/session/open")["due_reminders"], [])

    def test_consumed_schedule_is_not_exposed_as_pending_and_rebooking_rearms(self):
        self.start()
        scheduled = self.schedule()
        due_at = scheduled["task"]["start_due_at"]
        self.assertIsNotNone(due_at)
        before = self.snapshot()
        # 查询待提醒时间不消费，仍能到点取出。
        self.assertEqual(self.db.get_start_due_at(self.uid), due_at)
        self.assertEqual(self.snapshot(), before)
        self.now += timedelta(minutes=5)
        result = self.poll()
        self.assertEqual(len(result["due_reminders"]), 1)
        self.assertIsNone(result["task"]["start_due_at"])
        state = self.client.get("/api/session/state", params={"user_id": self.uid}).json()
        self.assertIsNone(state["task"]["start_due_at"])
        self.assertEqual(self.rows()[0]["notified"], 1)
        self.assertIsNone(DB(self.db.path).get_start_due_at(self.uid))
        self.assertIsNotNone(self.schedule(10)["task"]["start_due_at"])
        self.now += timedelta(minutes=10)
        self.assertEqual(len(self.poll()["due_reminders"]), 1)

    def test_open_consumes_schedule_and_returns_no_pending_deadline(self):
        self.start()
        self.schedule()
        self.now += timedelta(minutes=5)
        result = self.post("/api/session/open")
        self.assertEqual(len(result["due_reminders"]), 1)
        self.assertEqual(result["state"], "ready")
        self.assertIsNone(result["task"]["start_due_at"])
        self.assertEqual(self.poll()["due_reminders"], [])
        self.assertIsNone(self.db.get_start_due_at(self.uid))

    def test_rebooking_replaces_old_deadline_and_can_rearm_after_notification(self):
        self.start()
        self.schedule()
        self.now += timedelta(minutes=2)
        self.schedule(10)
        self.assertEqual(len(self.rows()), 1)
        self.now += timedelta(minutes=3)
        self.assertEqual(self.poll()["due_reminders"], [])
        self.now += timedelta(minutes=7)
        self.assertEqual(len(self.poll()["due_reminders"]), 1)
        self.schedule(5)
        self.now += timedelta(minutes=5)
        self.assertEqual(len(self.poll()["due_reminders"]), 1)

    def test_start_exit_replace_and_not_today_cancel_only_task_appointment(self):
        cases = [("/api/task/choose_time", {"when": "now"}),
                 ("/api/task/choose_time", {"when": "not_today"}),
                 ("/api/task/exit", {}),
                 ("/api/chat", {"message": "今天先到这吧"}),
                 ("/api/chat", {"message": "换成写论文"})]
        self.db.add_reminder(self.uid, "喝水", "2099-01-01T00:00:00")
        for path, payload in cases:
            with self.subTest(path=path, payload=payload):
                self.start()
                self.schedule()
                self.post(path, **payload)
                self.assertEqual(self.rows(), [])
                self.now += timedelta(minutes=11)
                self.assertEqual(self.poll()["due_reminders"], [])
        with self.db._conn() as c:
            self.assertEqual([r["label"] for r in c.execute("SELECT label FROM reminders")], ["喝水"])

    def test_resize_and_tired_feedback_preserve_deadline(self):
        self.start()
        self.schedule()
        before = self.rows()
        self.post("/api/step/resize", direction="smaller")
        self.post("/api/chat", message="我累了")
        self.assertEqual(self.rows(), before)

    def test_restart_preserves_deadline_and_open_delivers_once(self):
        self.start()
        self.schedule()
        restarted = DB(self.db.path)
        self.now += timedelta(minutes=5)
        with patch("app.services.db", restarted):
            self.assertEqual(len(self.post("/api/session/open")["due_reminders"]), 1)
            self.assertEqual(self.poll()["due_reminders"], [])

    def test_other_users_cannot_take_or_cancel_this_appointment(self):
        self.start()
        self.schedule()
        self.now += timedelta(minutes=5)
        for path in ("/api/reminders/poll", "/api/task/exit", "/api/session/open"):
            result = self.client.post(path, json={"user_id": "other-user"}).json()
            self.assertEqual(result["due_reminders"], [])
        self.assertEqual(len(self.poll()["due_reminders"]), 1)

    def test_parallel_takers_get_only_one_reminder(self):
        self.start()
        self.schedule()
        self.now += timedelta(minutes=5)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: DB(self.db.path).take_due_start_reminder(self.uid), range(4)))
        self.assertEqual(sum(len(r) for r in results), 1)

    def test_rollover_cancels_appointment_with_existing_task_cleanup(self):
        self.start()
        self.schedule()
        with self.db._conn() as c:
            c.execute("UPDATE users SET last_seen=? WHERE user_id=?",
                      ((datetime.now().date() - timedelta(days=1)).isoformat(), self.uid))
        self.now += timedelta(minutes=10)
        result = self.poll()
        self.assertEqual(result["state"], "idle")
        self.assertEqual(result["due_reminders"], [])
        self.assertEqual(self.rows(), [])

    def test_invalid_values_states_and_empty_poll_identity_do_not_write(self):
        self.start()
        self.schedule()
        before = self.snapshot()
        for value in ("in_30_minutes", 5, True, "TYPO"):
            response = self.client.post("/api/task/choose_time", json={"user_id": self.uid, "when": value})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.client.post("/api/reminders/poll", json={"user_id": " "}).status_code, 422)
        self.assertEqual(self.snapshot(), before)
        self.post("/api/task/choose_time", when="now")
        before = self.snapshot()
        self.assertEqual(self.client.post("/api/task/choose_time", json={"user_id": self.uid, "when": "in_5_minutes"}).status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_old_database_preserves_legacy_data_and_suppresses_old_thirty_minute_cues(self):
        self.start()
        self.db.add_reminder(self.uid, "该开始「旧任务」啦", "2000-01-01T00:00:00")
        self.db.add_reminder(self.uid, "喝水", "2000-01-01T00:00:00")
        with self.db._conn() as c:
            c.execute("DROP TABLE task_start_reminders")
            c.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, note TEXT)")
            c.execute("INSERT INTO journal VALUES (1, 'legacy-private-note')")
        restarted = DB(self.db.path)
        with patch("app.services.db", restarted):
            result = self.post("/api/session/open")
            self.assertEqual(result["due_reminders"], ["喝水"])
        with restarted._conn() as c:
            self.assertEqual(c.execute("SELECT note FROM journal").fetchone()[0], "legacy-private-note")
            self.assertEqual(c.execute("SELECT count(*) FROM reminders").fetchone()[0], 2)
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
