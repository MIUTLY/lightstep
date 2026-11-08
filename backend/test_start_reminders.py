"""取消计时后的兼容拒绝、手动推进、历史数据与跨天保留回归。"""
import os
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


class RemovedTimerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DB(str(Path(self.tmp.name) / "test.db"))
        self.a = patch("app.services.db", self.db)
        self.b = patch("app.services.llm", MockLLM())
        self.a.start(); self.b.start()
        self.client = TestClient(app)
        self.uid = "timer-user"

    def tearDown(self):
        self.client.close(); self.b.stop(); self.a.stop(); self.tmp.cleanup()

    def post(self, path, **payload):
        response = self.client.post('/api/' + path, json={"user_id": self.uid, **payload})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def start(self):
        return self.post('chat', workflow='legacy', message='换成写论文')

    def begin(self):
        self.start()
        prompt = self.post('task/choose_time', when='now')
        self.assertNotIn('5分钟', prompt['reply'])
        self.assertNotIn('五分钟', prompt['reply'])
        return self.post('task/commit', agree=True)

    def snapshot(self):
        with self.db._conn() as c:
            names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            return {n:[tuple(r) for r in c.execute('SELECT * FROM "'+n+'" ORDER BY rowid')] for n in names}

    def seed_old_reminders(self):
        with self.db._conn() as c:
            c.execute("INSERT INTO task_start_reminders (user_id,due_at,notified) VALUES (?, '2000-01-01T00:00:00', 0)", (self.uid,))
            c.execute("INSERT INTO reminders (user_id,label,due_at) VALUES (?, '旧提醒', '2000-01-01T00:00:00')", (self.uid,))

    def test_retired_schedule_options_fail_without_writes(self):
        self.start()
        before = self.snapshot()
        for when in ('in_5_minutes', 'in_10_minutes', 'later'):
            r = self.client.post('/api/task/choose_time', json={'user_id':self.uid, 'when':when})
            self.assertEqual(r.status_code, 410)
            self.assertEqual(r.json()['detail']['code'], 'TASK_TIMERS_REMOVED')
            self.assertEqual(self.snapshot(), before)

    def test_retired_poll_does_not_roll_over_or_consume_old_rows(self):
        self.begin(); self.seed_old_reminders()
        with self.db._conn() as c:
            c.execute("UPDATE users SET last_seen='2000-01-01' WHERE user_id=?", (self.uid,))
        before = self.snapshot()
        for _ in range(2):
            r = self.client.post('/api/reminders/poll', json={'user_id':self.uid})
            self.assertEqual(r.status_code, 410)
            self.assertEqual(self.snapshot(), before)

    def test_open_and_restart_never_deliver_historical_reminders(self):
        self.start(); self.seed_old_reminders()
        before = self.db.get_active_task(self.uid)
        with patch('app.services.db', DB(self.db.path)):
            for _ in range(2):
                r = self.post('session/open')
                self.assertEqual(r['due_reminders'], [])
                self.assertIsNone(r['task']['start_due_at'])
                self.assertEqual(r['buttons'], ['现在开始','今天不做'])
        self.assertEqual(self.db.get_active_task(self.uid), before)
        with self.db._conn() as c:
            self.assertEqual(c.execute('SELECT notified FROM task_start_reminders').fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT count(*) FROM reminders').fetchone()[0], 1)

    def test_completion_without_elapsed_advances_only_on_manual_request(self):
        r = self.begin(); before = r['task']
        for _ in range(2):
            self.assertEqual(self.post('session/open')['task'], before)
        r = self.post('step/complete', step_id=before['step_id'])
        self.assertGreater(r['task']['steps_done'], before['steps_done'])
        self.assertEqual(r['task']['granularity'], before['granularity'])
        again = self.client.post('/api/step/complete', json={'user_id':self.uid,'step_id':before['step_id']})
        self.assertEqual(again.status_code, 409)

    def test_old_elapsed_values_do_not_change_level_or_friction(self):
        for elapsed in (0, 3000, 999999999):
            self.begin()
            with self.db._conn() as c:
                before = [tuple(r) for r in c.execute('SELECT * FROM friction')]
            r = self.post('step/complete', duration_ms=elapsed)
            self.assertEqual(r['task']['granularity'], 'normal')
            with self.db._conn() as c:
                self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM friction')], before)

    def test_next_day_keeps_unstarted_and_started_tasks(self):
        for started in (False, True):
            self.begin() if started else self.start()
            if started: self.post('step/complete')
            before = self.db.get_active_task(self.uid)
            with self.db._conn() as c:
                c.execute("UPDATE users SET last_seen='2000-01-01' WHERE user_id=?", (self.uid,))
            self.post('session/open')
            self.assertEqual(self.db.get_active_task(self.uid), before)

    def test_completion_before_manual_start_still_rejected(self):
        self.start(); before = self.snapshot()
        r = self.client.post('/api/step/complete', json={'user_id':self.uid})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_timer_inputs_are_rejected_without_writes(self):
        self.begin(); before = self.snapshot()
        for elapsed in (-1, True, '100', 1.5):
            r = self.client.post('/api/step/complete', json={'user_id':self.uid,'duration_ms':elapsed})
            self.assertEqual(r.status_code, 422)
            self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
