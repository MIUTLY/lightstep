"""任务保护、参数拒绝及状态转换回归；全部使用离线模型和临时数据库。"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-flow-boot-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "openai"

from fastapi.testclient import TestClient
from app.db import DB
from tests.fakes import MockLLM
from app.main import app


class TaskFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lightstep-flow-")
        self.db = DB(str(Path(self.tmp.name) / "test.db"))
        self.llm = MockLLM()
        self.db_patch = patch("app.services.db", self.db)
        self.llm_patch = patch("app.services.llm", self.llm)
        self.db_patch.start()
        self.llm_patch.start()
        self.client = TestClient(app)
        self.uid = "flow-user"

    def tearDown(self):
        self.client.close()
        self.llm_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def post(self, path, **payload):
        return self.client.post(path, json={"user_id": self.uid, **({"workflow":"legacy"} if path.endswith("chat") else {}), **payload})

    def task(self, state="executing"):
        self.db.clear_active_task(self.uid)
        self.assertEqual(self.post("/api/chat", message="写课程论文").status_code, 200)
        if state in ("committing", "executing"):
            self.assertEqual(self.post("/api/task/choose_time", when="now").status_code, 200)
        if state == "executing":
            self.assertEqual(self.post("/api/task/commit", agree=True).status_code, 200)

    def snapshot(self):
        # 包括用户、任务、偏好、便签与提醒，拒绝请求不能偷改任何这些数据。
        with self.db._conn() as c:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(r) for r in c.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
                    for name in tables}

    def test_questions_and_ambiguous_new_goals_keep_task_and_progress(self):
        for state in ("ready", "committing", "executing"):
            self.task(state)
            if state == "executing":
                self.post("/api/step/complete", duration_ms=30000)
            before = self.snapshot()
            task = self.db.get_active_task(self.uid)
            for message in ("这一步要怎么做", "写不出来该怎么办", "这一步可以换一个方法吗", "换一个方法试试", "做完以后怎么结束？", "这步的结束条件是什么", "我想背单词"):
                with self.subTest(state=state, message=message), \
                     patch.object(self.llm, "decompose", wraps=self.llm.decompose) as planning, \
                     patch.object(self.llm, "reply", return_value="我们看看眼前这一步。") as reply:
                    response = self.post("/api/chat", message=message)
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    self.assertEqual(data["state"], state)
                    self.assertEqual(data["task"]["title"], task["title"])
                    self.assertEqual(data["task"]["steps_done"], task["steps_done"])
                    self.assertEqual(self.snapshot(), before)
                    planning.assert_not_called()
                    self.assertIn(task["title"], reply.call_args.args[0])

    def test_explicit_switch_can_replace_task(self):
        for message in ("换成背单词", "请换成背单词", "我想换成背单词"):
            self.task()
            response = self.post("/api/chat", message=message)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["state"], "ready")
            self.assertEqual(response.json()["task"]["title"], "背单词")

    def test_switch_without_target_asks_without_clearing_task(self):
        self.task()
        before = self.snapshot()
        for message in ("换个任务", "请换个任务", "换一个"):
            response = self.post("/api/chat", message=message)
            self.assertEqual(response.json()["state"], "executing")
            self.assertIsNotNone(response.json()["task"])
            self.assertEqual(self.snapshot(), before)

    def test_explicit_polite_resize_question_still_adjusts_step(self):
        self.task()
        response = self.post("/api/chat", message="这步太重了，能拆小一点吗")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "executing")
        self.assertEqual(response.json()["task"]["granularity"], "fine")

    def test_empty_user_ids_are_rejected_before_any_storage(self):
        before = self.snapshot()
        self.assertEqual(self.client.post("/api/session/open", json={"user_id": "  "}).status_code, 422)
        for path in ("/api/session/state", "/api/history", "/api/daily/summary"):
            self.assertEqual(self.client.get(path, params={"user_id": " "}).status_code, 422)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_parameters_are_422_and_leave_database_unchanged(self):
        self.task()
        before = self.snapshot()
        invalid = [
            ("/api/step/complete", {"duration_ms": -1}),
            ("/api/step/complete", {"duration_ms": True}),
            ("/api/step/complete", {"duration_ms": "3000"}),
            ("/api/step/complete", {"duration_ms": 1.5}),
            ("/api/task/choose_time", {"when": "TYPO"}),
            ("/api/step/resize", {"direction": "TYPO"}),
            ("/api/task/commit", {"agree": "true"}),
            ("/api/task/exit", {"gentle": "false"}),
            ("/api/chat", {"workflow": "legacy", "message": "   "}),
            ("/api/note", {"content": "   "}),
        ]
        for path, payload in invalid:
            with self.subTest(path=path, payload=payload):
                self.assertEqual(self.post(path, **payload).status_code, 422)
                self.assertEqual(self.snapshot(), before)

    def test_invalid_states_are_409_and_leave_database_unchanged(self):
        cases = [
            ("ready", "/api/task/commit", {"agree": True}),
            ("ready", "/api/step/complete", {"duration_ms": 3000}),
            ("committing", "/api/step/complete", {"duration_ms": 3000}),
            ("executing", "/api/task/choose_time", {"when": "now"}),
            ("executing", "/api/task/choose_time", {"when": "not_today"}),
            ("executing", "/api/task/commit", {"agree": False}),
        ]
        for state, path, payload in cases:
            self.db.clear_active_task(self.uid)
            self.task(state)
            before = self.snapshot()
            with self.subTest(state=state, path=path):
                response = self.post(path, **payload)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["detail"]["code"], "INVALID_TASK_STATE")
                self.assertEqual(self.snapshot(), before)

    def test_command_without_task_does_not_even_create_user(self):
        before = self.snapshot()
        for path, payload in [("/api/task/choose_time", {"when": "now"}),
                ("/api/task/commit", {"agree": True}),
                ("/api/step/complete", {"duration_ms": 0}),
                ("/api/step/resize", {"direction": "smaller"})]:
            with self.subTest(path=path):
                self.assertEqual(self.post(path, **payload).status_code, 409)
                self.assertEqual(self.snapshot(), before)

    def test_resize_before_start_preserves_ready_or_committing(self):
        for state in ("ready", "committing"):
            self.db.clear_active_task(self.uid)
            self.task(state)
            response = self.post("/api/step/resize", direction="smaller")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["state"], state)
            self.assertEqual(response.json()["task"]["state"], state)
            self.assertEqual(self.db.get_active_task(self.uid)["state"], state)

    def test_normal_start_complete_and_exit_still_work(self):
        self.task()
        response = self.post("/api/step/complete", duration_ms=30000)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["steps_done"], 1)
        self.assertEqual(self.post("/api/task/exit").json()["state"], "idle")

    def test_declining_commit_returns_consistent_ready_state(self):
        self.task("committing")
        response = self.post("/api/task/commit", agree=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "ready")
        self.assertEqual(response.json()["task"]["state"], "ready")
        self.assertEqual(self.db.get_active_task(self.uid)["state"], "ready")


if __name__ == "__main__":
    unittest.main()
