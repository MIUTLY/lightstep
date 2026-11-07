"""轻步 LightStep 后端冒烟测试（显式注入测试替身，不验证真实AI）。

跑一遍现有任务流程、摩擦地图与跨天交接；确认服务端手帐已停用。
"""
import os
from pathlib import Path
import tempfile
import sys
import time
from unittest.mock import patch
from tests.fakes import MockLLM
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

_smoke_dir = tempfile.TemporaryDirectory(prefix="lightstep-smoke-")
os.environ["LIGHTSTEP_DB"] = str(Path(_smoke_dir.name) / "smoke.db")

from app.main import app
from app.db import db

client = TestClient(app)


def show(label, resp):
    data = resp.json()
    print(f"\n[{label}]")
    print("  reply:", data.get("reply"))
    print("  state:", data.get("state"))
    if data.get("task"):
        print("  task:", data["task"])
    if data.get("buttons"):
        print("  buttons:", data["buttons"])
    if data.get("summary"):
        print("  summary:", data["summary"])
    return data


def main():
    uid = f"smoke_{int(time.time())}"
    print(f"===== 主流程（用户 {uid}）=====")
    show("打开", client.post("/api/session/open", json={"user_id": uid}))
    show("想写论文", client.post("/api/chat", json={"user_id": uid, "workflow": "legacy", "message": "好，那我试试写课程论文"}))
    show("现在开始", client.post("/api/task/choose_time", json={"user_id": uid, "when": "now"}))
    show("同意5分钟", client.post("/api/task/commit", json={"user_id": uid, "agree": True}))
    show("完成一步(快)", client.post("/api/step/complete", json={"user_id": uid, "duration_ms": 5000}))
    show("完成一步(快)", client.post("/api/step/complete", json={"user_id": uid, "duration_ms": 4000}))
    show("温柔收尾", client.post("/api/task/exit", json={"user_id": uid, "gentle": True}))

    # 手帐转为客户端本地存储，旧接口不再接收留言。
    print("\n===== 服务端手帐已停用 =====")
    retired = client.post("/api/journal/add", json={"user_id": uid, "note": "test-only"})
    assert retired.status_code == 410
    assert retired.json()["detail"]["code"] == "JOURNAL_CLIENT_ONLY"
    assert client.get("/api/journal", params={"user_id": uid}).status_code == 410

    # ===== 摩擦地图 =====
    print("\n===== 摩擦地图 =====")
    uid2 = f"friction_{int(time.time())}"
    client.post("/api/session/open", json={"user_id": uid2})
    show("背单词", client.post("/api/chat", json={"user_id": uid2, "workflow": "legacy", "message": "背单词"}))
    show("现在开始", client.post("/api/task/choose_time", json={"user_id": uid2, "when": "now"}))
    show("同意", client.post("/api/task/commit", json={"user_id": uid2, "agree": True}))
    for i in range(3):
        show(f"太重了(第{i + 1}次)", client.post("/api/step/resize", json={"user_id": uid2, "direction": "smaller"}))
    client.post("/api/task/exit", json={"user_id": uid2})
    r = show("再背单词", client.post("/api/chat", json={"user_id": uid2, "workflow": "legacy", "message": "背单词"}))
    assert r["task"]["granularity"] == "normal", "新森林按产品规则始终从中档开始，保留摩擦记录但不覆盖默认档位"

    # ===== 跨天温柔交接 =====
    print("\n===== 跨天温柔交接 =====")
    uid3 = f"handoff_{int(time.time())}"
    client.post("/api/session/open", json={"user_id": uid3})
    show("写日记", client.post("/api/chat", json={"user_id": uid3, "workflow": "legacy", "message": "写日记"}))
    show("现在开始", client.post("/api/task/choose_time", json={"user_id": uid3, "when": "now"}))
    show("同意", client.post("/api/task/commit", json={"user_id": uid3, "agree": True}))
    show("完成一步", client.post("/api/step/complete", json={"user_id": uid3, "duration_ms": 30000}))

    # 模拟昨天关掉应用：把 last_seen 改成昨天
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    with db._conn() as c:
        c.execute("UPDATE users SET last_seen=? WHERE user_id=?", (yesterday, uid3))
    print("\n[已把 last_seen 改成昨天]")

    h = show("第二天打开", client.post("/api/session/open", json={"user_id": uid3}))
    assert "接着" in h.get("reply", ""), "应出现跨天交接提示"
    show("接着做", client.post("/api/handoff/resume", json={"user_id": uid3}))

    print("\n✅ 全部 smoke test 通过")


if __name__ == "__main__":
    try:
        with patch("app.services.llm", MockLLM()):
            main()
    finally:
        client.close()
        _smoke_dir.cleanup()
