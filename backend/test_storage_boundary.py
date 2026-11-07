"""验证服务端任务状态与客户端手帐的数据边界。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

# 应用首次导入也只能创建临时数据库。
_boot_dir = tempfile.TemporaryDirectory(prefix="lightstep-boundary-boot-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot_dir.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "openai"

from fastapi.testclient import TestClient
from tests.fakes import MockLLM
from app.db import DB
from app.main import app


class StorageBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lightstep-boundary-")
        self.db = DB(str(Path(self.tmp.name) / "test.db"))
        self.swap = patch("app.services.db", self.db)
        self.swap.start()
        self.fake = patch("app.services.llm", MockLLM())
        self.fake.start()
        self.client = TestClient(app)
        self.uid = "boundary-test"

    def tearDown(self):
        self.client.close()
        self.swap.stop()
        self.fake.stop()
        self.tmp.cleanup()

    def start_task(self):
        for path, payload in [
            ("/api/session/open", {}),
            ("/api/chat", {"workflow": "legacy", "message": "背单词"}),
            ("/api/task/choose_time", {"when": "now"}),
            ("/api/task/commit", {"agree": True}),
        ]:
            response = self.client.post(path, json={"user_id": self.uid, **({"workflow":"legacy"} if path.endswith("chat") else {}), **payload})
            self.assertEqual(response.status_code, 200)

    def assert_no_server_journal(self):
        with self.db._conn() as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("journal", tables)

    def test_task_is_recoverable_from_server_without_client_progress(self):
        self.start_task()
        self.client.post("/api/step/complete", json={"user_id": self.uid, "duration_ms": 30000})
        state = self.client.get("/api/session/state", params={"user_id": self.uid}).json()
        self.assertEqual(state["state"], "executing")
        self.assertEqual(state["task"]["steps_done"], 1)
        reopened = self.client.post("/api/session/open", json={"user_id": self.uid}).json()
        self.assertEqual(reopened["task"], state["task"])
        self.assert_no_server_journal()

    def test_completing_task_does_not_save_receipt(self):
        self.start_task()
        # 按公开流程完成，避免依赖旧三清单的内部游标。
        for _ in range(30):
            r = self.client.post("/api/step/complete", json={"user_id": self.uid, "duration_ms": 30000})
            if r.json()["state"] == "done":
                break
        self.assertEqual(r.json()["state"], "done")
        self.assertIsNone(self.db.get_active_task(self.uid))
        self.assert_no_server_journal()

    def test_notes_preserve_authoritative_task_state(self):
        self.start_task()
        expected = self.client.get("/api/session/state", params={"user_id": self.uid}).json()
        for path, payload in [("/api/note", {"content": "取快递"}),
                              ("/api/chat", {"workflow": "legacy", "message": "帮我记一下取快递"})]:
            reply = self.client.post(path, json={"user_id": self.uid, **({"workflow":"legacy"} if path.endswith("chat") else {}), **payload}).json()
            self.assertEqual(reply["state"], expected["state"])
            self.assertEqual(reply["task"], expected["task"])
            self.assertEqual(self.client.get("/api/session/state",
                params={"user_id": self.uid}).json(), expected)

    def test_exiting_after_progress_does_not_save_receipt(self):
        self.start_task()
        self.client.post("/api/step/complete", json={"user_id": self.uid, "duration_ms": 30000})
        r = self.client.post("/api/task/exit", json={"user_id": self.uid})
        self.assertEqual(r.json()["state"], "idle")
        self.assertIsNone(self.db.get_active_task(self.uid))
        self.assert_no_server_journal()

    def test_retired_endpoints_neither_write_nor_delete_legacy_entries(self):
        # 不自动销毁旧数据库中已有的私人内容。
        with self.db._conn() as c:
            c.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, note TEXT)")
            c.execute("INSERT INTO journal VALUES (1, 'legacy-test-note')")
        requests = [
            self.client.get("/api/journal", params={"user_id": self.uid}),
            self.client.post("/api/journal/add", json={"user_id": self.uid, "note": "new-test-note"}),
            self.client.delete("/api/journal/1", params={"user_id": self.uid}),
        ]
        for r in requests:
            self.assertEqual(r.status_code, 410)
            self.assertEqual(r.json()["detail"]["code"], "JOURNAL_CLIENT_ONLY")
        with self.db._conn() as c:
            self.assertEqual([tuple(r) for r in c.execute("SELECT * FROM journal")], [(1, "legacy-test-note")])

    def test_cors_allows_configured_frontend(self):
        r = self.client.options("/api/chat", headers={"Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_api_only_deployment_keeps_api_and_disables_debug_page(self):
        env = dict(os.environ, LIGHTSTEP_SERVE_DEBUG_UI="false",
            LIGHTSTEP_DB=str(Path(self.tmp.name) / "api-only.db"))
        code = """
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
assert c.get('/api/health').json()['receipt_storage'] == 'client'
assert c.get('/').status_code == 404
assert c.get('/docs').status_code == 200
"""
        r = subprocess.run([sys.executable, "-c", code], env=env,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
