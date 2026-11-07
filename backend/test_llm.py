"""真实适配器协议与失败回归；HTTP仅用隔离替身，不调用供应商。"""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-llm-unit-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "openai"

import httpx
from fastapi.testclient import TestClient
from app.config import Settings
from app.db import DB
from app.llm import OpenAICompatLLM, AIError
from app.main import app
import check_llm


class LLMTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(llm_provider="openai", llm_api_key="test-key-not-real",
                                 llm_thinking="disabled", llm_max_tokens=512, llm_decompose_max_tokens=768)
        self.llm = OpenAICompatLLM(self.settings)

    def response(self, content, finish_reason="stop"):
        return httpx.Response(200, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
            json={"choices": [{"workflow": "legacy", "message": {"content": content}, "finish_reason": finish_reason}]})

    def test_json_request_has_budget_and_optional_vendor_controls(self):
        response = self.response(json.dumps({"trees": [{"text": "写一段", "children": [{"text": "写一句", "children": [{"text": "开文档"}]}]}]}))
        with patch("httpx.post", side_effect=[response, self.response(json.dumps({
                "decision": "accept", "relevant": True, "coverage": True,
                "parent_child_consistent": True, "no_duplicates": True}))]) as post:
            result = self.llm.decompose("写论文")
        self.assertEqual(result["trees"][0]["children"][0]["text"], "写一句")
        kwargs = post.call_args_list[0].kwargs
        self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["json"]["thinking"], {"type": "disabled"})
        self.assertEqual(kwargs["json"]["max_tokens"], 768)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key-not-real")

    def test_generic_provider_does_not_receive_thinking_when_unconfigured(self):
        client = OpenAICompatLLM(Settings(llm_api_key="test", llm_thinking=""))
        with patch("httpx.post", return_value=self.response("好")) as post:
            client._chat("system", "user")
        self.assertNotIn("thinking", post.call_args.kwargs["json"])

    def test_bad_model_steps_cannot_cause_task_creation_500(self):
        invalid = [[], {"fine": [], "normal": [42], "coarse": []},
            {"fine": ["打开"], "normal": [" "], "coarse": ["写完"]}]
        with tempfile.TemporaryDirectory(prefix="lightstep-bad-model-") as tmp:
            db = DB(str(Path(tmp) / "test.db"))
            with patch("app.services.db", db), patch("app.services.llm", self.llm), \
                 patch.object(self.llm, "detect_emotion", return_value="正常"), TestClient(app) as client:
                for index, data in enumerate(invalid):
                    with self.subTest(data=data), patch.object(self.llm, "_chat", return_value=json.dumps(data)):
                        response = client.post("/api/chat", json={"user_id": f"invalid-{index}", "workflow": "legacy", "message": "写论文"})
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()["state"], "idle")
                        self.assertEqual(response.json()["generation"]["status"], "failed")
                        self.assertIsNone(db.get_active_task(f"invalid-{index}"))

    def test_truncated_generation_is_rejected(self):
        with patch("httpx.post", return_value=self.response("{", "length")):
            with self.assertRaises(AIError):
                self.llm._chat("system", "user", json_mode=True)

    def test_error_does_not_include_key_or_provider_body(self):
        with patch("httpx.post", side_effect=httpx.ConnectError("test-key-not-real private response")):
            with self.assertRaises(AIError) as caught:
                self.llm.reply("idle", "你好")
        self.assertNotIn("test-key-not-real", str(caught.exception))
        self.assertNotIn("private response", str(caught.exception))

    def test_probe_reports_failure_instead_of_offline_success(self):
        output = io.StringIO()
        with patch("check_llm.settings", self.settings), patch("sys.argv", ["check_llm.py"]), \
             patch.object(OpenAICompatLLM, "_chat", side_effect=httpx.ConnectTimeout("test timeout")), \
             contextlib.redirect_stdout(output):
            code = check_llm.main()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "remote_failed")


if __name__ == "__main__":
    unittest.main()
