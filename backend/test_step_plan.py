"""验证粒度变化前后动作不跳过、不重做；使用mock模型和临时数据库。"""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-plan-boot-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "openai"

from fastapi.testclient import TestClient
from app.db import DB
from tests.fakes import MockLLM
from app.main import app
from app import services, step_plan


class StepPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lightstep-plan-")
        self.db = DB(str(Path(self.tmp.name) / "test.db"))
        self.llm = MockLLM()
        self.a = patch("app.services.db", self.db)
        self.b = patch("app.services.llm", self.llm)
        self.a.start()
        self.b.start()
        self.client = TestClient(app)
        self.uid = "plan-user"

    def tearDown(self):
        self.client.close()
        self.b.stop()
        self.a.stop()
        self.tmp.cleanup()

    def post(self, path, **data):
        result = self.client.post(path, json={"user_id": self.uid, **({"workflow":"legacy"} if path.endswith("chat") else {}), **data})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def start(self, title="背单词", normal=None):
        # 这些是旧队列的兼容回归；新建森林的产品规则在test_task_forest覆盖。
        from tests.fakes import decompose
        levels = decompose(title) if normal is None else {"fine": ["另一套细清单"], "normal": normal, "coarse": ["另一套粗清单"]}
        self.db.ensure_user(self.uid)
        self.db.create_active_task(self.uid, title, json.dumps(step_plan.new_plan(levels, 2)), 2, state="ready")
        self.post("/api/task/choose_time", when="now")
        return self.post("/api/task/commit", agree=True)

    def state(self):
        return self.client.get("/api/session/state", params={"user_id": self.uid}).json()

    def test_fast_opening_keeps_manual_level_and_next_action(self):
        self.start()
        reply = self.post("/api/step/complete", duration_ms=3000)
        self.assertEqual(reply["state"], "executing")
        self.assertIn("过 5 个单词", reply["task"]["current_step"])
        self.assertNotIn("把记不住的标出来", reply["task"]["current_step"])
        self.assertEqual(reply["task"]["granularity"], "normal")
        self.assertEqual(self.db.get_active_task(self.uid)["current_idx"], 1)

    def test_resize_does_not_move_cursor_or_reopen_completed_prefix(self):
        self.start()
        self.post("/api/step/complete", duration_ms=30000)
        before = self.db.get_active_task(self.uid)
        prefix = step_plan.ensure_plan(before)[step_plan.PLAN_KEY]["units"][:before["current_idx"]]
        for direction in ("bigger", "smaller", "smaller", "smaller"):
            reply = self.post("/api/step/resize", direction=direction)
            after = self.db.get_active_task(self.uid)
            units = step_plan.ensure_plan(after)[step_plan.PLAN_KEY]["units"]
            self.assertEqual(after["current_idx"], before["current_idx"])
            self.assertEqual(after["steps_done"], before["steps_done"])
            self.assertEqual(units[:after["current_idx"]], prefix)
            self.assertNotIn("打开单词本", reply["task"]["current_step"])

    def test_mixed_resizes_complete_every_ordered_action_once(self):
        route = ["动作A", "动作B", "动作C", "动作D", "动作E"]
        self.start(normal=route)
        completed = []
        operations = [("bigger",), ("smaller", "smaller"), ("bigger", "bigger"), ()]
        for index in range(10):
            if self.state()["state"] == "idle":
                break
            for direction in operations[index % len(operations)]:
                self.post("/api/step/resize", direction=direction)
            task = self.db.get_active_task(self.uid)
            levels = step_plan.ensure_plan(task)
            completed.extend(u["text"] for u in step_plan.displayed_units(levels, task["current_idx"]))
            self.post("/api/step/complete", duration_ms=30000)
        self.assertEqual(completed, route)
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_splitting_counts_preserves_total_and_delays_final_marking(self):
        self.start(normal=["过 5 个单词，遮住中文回忆", "标记卡住的词"])
        self.post("/api/step/resize", direction="smaller")
        total = 0
        ids = []
        for _ in range(20):
            current = self.state()["task"]
            if current is None:
                break
            ids.append(current["step_id"])
            text = current["current_step"]
            if "标记" in text:
                self.assertEqual(total, 5)
            total += sum(int(n) for n in re.findall(r"过\s+(\d+)\s*个单词", text))
            self.post("/api/step/complete", duration_ms=120000)
        self.assertEqual(total, 5)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_identical_visible_text_has_different_ids_for_different_steps(self):
        self.start(normal=["读一小段", "读一小段", "写一句小结"])
        before = self.state()["task"]
        after = self.post("/api/step/complete", duration_ms=30000)["task"]
        self.assertEqual(before["current_step"], after["current_step"])
        self.assertNotEqual(before["step_id"], after["step_id"])
        self.assertEqual(after["step_id"], self.state()["task"]["step_id"])

    def test_legacy_task_continues_current_list_without_replaying_completed_steps(self):
        levels = {"fine": ["细A", "细B", "细C", "细D"], "normal": ["旧A", "旧B", "旧C"], "coarse": ["粗A", "粗B"]}
        self.db.create_active_task(self.uid, "旧任务", json.dumps(levels), 2,
                                   current_idx=1, steps_done=1, state="executing")
        self.assertEqual(self.state()["task"]["current_step"], "旧B")
        reply = self.post("/api/step/complete", duration_ms=3000)
        self.assertEqual(reply["task"]["current_step"], "旧C")
        self.assertEqual(reply["task"]["steps_done"], 2)

    def test_handoff_roundtrip_preserves_displayed_batch_and_id(self):
        self.start()
        before = self.post("/api/step/complete", duration_ms=3000)["task"]
        task = self.db.get_active_task(self.uid)
        self.db._save_handoff_from_task(self.uid, task)
        self.db.clear_active_task(self.uid)
        handoff = self.db.get_handoff(self.uid)
        self.assertEqual(services._handoff_last_step(handoff), before["current_step"])
        after = self.post("/api/handoff/resume")["task"]
        self.assertEqual(before["step_id"], after["step_id"])
        self.assertEqual(before["current_step"], after["current_step"])

    def test_legacy_handoff_without_date_is_readable(self):
        legacy = {"title": "旧任务", "saved_date": "2026-11-06", "level": 2, "current_idx": 1,
                  "levels_json": json.dumps({"normal": ["旧A", "旧B"]})}
        self.assertEqual(services._handoff_last_step(legacy), "旧B")

    def test_small_session_completion_does_not_claim_whole_large_goal_done(self):
        self.start(title="背50个单词", normal=["过 5 个单词"])
        reply = self.post("/api/step/complete", duration_ms=30000)
        self.assertEqual(reply["state"], "done")
        self.assertIn("这一小段", reply["reply"])
        self.assertNotIn("背50个单词", reply["reply"])

    def test_resize_does_not_call_model_again(self):
        self.start()
        with patch.object(self.llm, "decompose", side_effect=AssertionError("no replanning")):
            for direction in ("smaller", "bigger", "bigger", "smaller"):
                self.post("/api/step/resize", direction=direction)

    def test_quantity_split_is_conservative_and_avoids_ordinals_and_conditions(self):
        for count in range(2, 25):
            parts = step_plan.split_action(f"背{count}个单词")
            self.assertEqual(sum(int(re.search(r"\d+", part).group()) for part in parts), count)
        for text in ("读第5页", "读第 5 页", "如果没报错，就写5句话", "打开单词本",
                     "读1.5页", "读1/2页", "读5-10页", "背1,000个单词", "背一百二十个单词"):
            self.assertIsNone(step_plan.split_action(text))

    def test_splitting_compound_work_does_not_duplicate_followup_action(self):
        self.start(normal=["写三句话，再通读一遍"])
        self.post("/api/step/resize", direction="smaller")
        read_count = 0
        written = 0
        for _ in range(10):
            current = self.state()["task"]
            if current is None:
                break
            text = current["current_step"]
            read_count += text.count("通读一遍")
            written += sum(int(n) for n in re.findall(r"写(\d+)句话", text))
            self.post("/api/step/complete", duration_ms=120000)
        self.assertEqual(written, 3)
        self.assertEqual(read_count, 1)


if __name__ == "__main__":
    unittest.main()
