"""自然收尾与疲惫反馈：HTTP状态、进度和全库副作用回归。"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-ending-boot-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from app.db import DB
from app.llm import MockLLM
from app.main import app


class EndingIntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lightstep-ending-")
        self.db = DB(str(Path(self.tmp.name) / "test.db"))
        self.llm = MockLLM()
        self.db_patch = patch("app.services.db", self.db)
        self.llm_patch = patch("app.services.llm", self.llm)
        self.db_patch.start()
        self.llm_patch.start()
        self.client = TestClient(app)
        self.uid = "ending-user"

    def tearDown(self):
        self.client.close()
        self.llm_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def post(self, path, **payload):
        response = self.client.post(path, json={"user_id": self.uid, **payload})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def start(self, state="executing"):
        self.db.clear_active_task(self.uid)
        self.post("/api/chat", message="写课程论文")
        if state in ("committing", "executing"):
            self.post("/api/task/choose_time", when="now")
        if state == "executing":
            self.post("/api/task/commit", agree=True)
            self.post("/api/step/complete", duration_ms=30000)

    def snapshot(self):
        with self.db._conn() as c:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(r) for r in c.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
                    for name in tables}

    def assert_kept(self, message, state="executing"):
        before = self.snapshot()
        task = self.client.get("/api/session/state", params={"user_id": self.uid}).json()["task"]
        result = self.post("/api/chat", message=message)
        self.assertEqual(result["state"], state)
        self.assertEqual(result["task"], task)
        self.assertEqual(self.snapshot(), before)
        return result

    def test_tired_feedback_offers_choice_without_writing_or_calling_model(self):
        for state in ("ready", "committing", "executing"):
            self.start(state)
            for message in ("我累了", "我有点累了", "我太累了", "这一步做不动了", "我想先休息一下", "我想休息", "先休息吧", "我累了，想休息一会儿"):
                with self.subTest(state=state, message=message), \
                     patch.object(self.llm, "detect_emotion", side_effect=AssertionError("unexpected model call")), \
                     patch.object(self.llm, "decompose", side_effect=AssertionError("unexpected model call")), \
                     patch.object(self.llm, "reply", side_effect=AssertionError("unexpected model call")):
                    data = self.assert_kept(message, state)
                    self.assertEqual(data["buttons"], ["今天到这吧", "太重了"])
                    self.assertIn("进度先留着", data["reply"])

    def test_explicit_closing_clears_only_active_task(self):
        for state in ("ready", "committing", "executing"):
            for message in ("今天先到这吧", "我今天就先到这里吧", "那就先到这吧", "请结束当前任务", "结束", "我想结束了", "温柔收尾", "我不想做了", "我累了，今天先到这吧", "今天什么都不想干", "今天休息", "好，收工吧，谢谢"):
                with self.subTest(state=state, message=message):
                    self.start(state)
                    self.db.add_note(self.uid, "取快递")
                    self.db.add_reminder(self.uid, "喝水", "2099-01-01T00:00:00")
                    before = self.snapshot()
                    data = self.post("/api/chat", message=message)
                    self.assertEqual(data["state"], "idle")
                    self.assertIsNone(data["task"])
                    self.assertEqual(data["buttons"], [])
                    self.assertIsNone(self.db.get_active_task(self.uid))
                    after = self.snapshot()
                    self.assertEqual(after.pop("active_task"), [])
                    before.pop("active_task")
                    self.assertEqual(after, before)
                    self.assertNotIn("journal", after)

    def test_negation_condition_future_quote_and_topic_do_not_end_task(self):
        self.start()
        for message in ("不要结束", "我不想结束", "今天不想结束，我还想继续", "我不是不想做了", "我不累了，继续", "如果累了就结束", "等这一步做完再结束", "明天再休息", "我在写一个关于结束的句子", "收工时间是六点", "屏幕上写着‘今天到这吧’", "‘结束’", "今天什么都不想干是小说标题"):
            with self.subTest(message=message):
                self.assert_kept(message)

    def test_questions_about_ending_remain_questions(self):
        self.start()
        for message in ("怎么结束任务？", "这步的结束条件是什么", "我可以结束吗", "今天先到这吧？", "我累了怎么办", "为什么我总想休息", "今天什么都不想干怎么办"):
            with self.subTest(message=message), patch.object(self.llm, "reply", return_value="想结束时可以点收尾按钮。"):
                self.assert_kept(message)

    def test_notes_containing_end_words_are_saved_without_ending(self):
        self.start()
        task = self.db.get_active_task(self.uid)
        for message in ("帮我记一下今天到这吧这句台词", "记一下六点结束", "提醒我今天休息"):
            data = self.post("/api/chat", message=message)
            self.assertEqual(data["state"], "executing")
            self.assertEqual(self.db.get_active_task(self.uid), task)
        self.assertEqual(len(self.db.get_pending_notes(self.uid)), 3)

    def test_explicit_resize_overrides_tired_topic(self):
        self.start()
        data = self.post("/api/chat", message="我太累了，能不能拆小一点吗")
        self.assertEqual(data["state"], "executing")
        self.assertEqual(data["task"]["granularity"], "fine")
        self.assertEqual(data["task"]["steps_done"], 1)

    def test_tired_choice_can_end_or_resize_via_existing_actions(self):
        self.start()
        self.post("/api/chat", message="我累了")
        data = self.post("/api/step/resize", direction="smaller")
        self.assertEqual(data["state"], "executing")
        self.assertEqual(data["task"]["steps_done"], 1)
        self.post("/api/chat", message="我累了")
        data = self.post("/api/task/exit", gentle=True)
        self.assertEqual(data["state"], "idle")
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_tired_or_end_when_idle_does_not_create_goal(self):
        self.post("/api/session/open")
        before = self.snapshot()
        for message in ("我累了", "我想休息一下", "我想先歇一会儿", "今天先到这吧", "结束"):
            with self.subTest(message=message), patch.object(self.llm, "decompose", side_effect=AssertionError("unexpected new goal")):
                data = self.post("/api/chat", message=message)
                self.assertEqual(data["state"], "idle")
                self.assertIsNone(data["task"])
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
