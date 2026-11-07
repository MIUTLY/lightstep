"""轻步 LightStep 后端冒烟测试（离线，无需 key）。

跑一遍完整流程 + 三个新功能（摩擦地图 / 跨天交接 / 私人手帐）。
"""
import sys
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

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
    show("想写论文", client.post("/api/chat", json={"user_id": uid, "message": "好，那我试试写课程论文"}))
    show("现在开始", client.post("/api/task/choose_time", json={"user_id": uid, "when": "now"}))
    show("同意5分钟", client.post("/api/task/commit", json={"user_id": uid, "agree": True}))
    show("完成一步(快)", client.post("/api/step/complete", json={"user_id": uid, "duration_ms": 5000}))
    show("完成一步(快)", client.post("/api/step/complete", json={"user_id": uid, "duration_ms": 4000}))
    show("温柔收尾", client.post("/api/task/exit", json={"user_id": uid, "gentle": True}))

    # ===== 私人静默手帐 =====
    print("\n===== 私人静默手帐 =====")
    j = client.get("/api/journal", params={"user_id": uid}).json()
    print("[手帐列表]", j)
    assert isinstance(j, list) and len(j) >= 1, "手帐应有自动回执"
    added = client.post("/api/journal/add", json={"user_id": uid, "note": "今天其实有点累"}).json()
    print("[手帐新增]", added)
    assert added["id"]
    deleted = client.delete(f"/api/journal/{added['id']}", params={"user_id": uid}).json()
    print("[手帐删除]", deleted)
    assert deleted["deleted"] is True

    # ===== 摩擦地图 =====
    print("\n===== 摩擦地图 =====")
    uid2 = f"friction_{int(time.time())}"
    client.post("/api/session/open", json={"user_id": uid2})
    show("背单词", client.post("/api/chat", json={"user_id": uid2, "message": "背单词"}))
    show("现在开始", client.post("/api/task/choose_time", json={"user_id": uid2, "when": "now"}))
    show("同意", client.post("/api/task/commit", json={"user_id": uid2, "agree": True}))
    for i in range(3):
        show(f"太重了(第{i + 1}次)", client.post("/api/step/resize", json={"user_id": uid2, "direction": "smaller"}))
    client.post("/api/task/exit", json={"user_id": uid2})
    r = show("再背单词", client.post("/api/chat", json={"user_id": uid2, "message": "背单词"}))
    assert r["task"]["granularity"] == "fine", f"摩擦地图应让默认粒度变细，实际 {r['task']['granularity']}"

    # ===== 跨天温柔交接 =====
    print("\n===== 跨天温柔交接 =====")
    uid3 = f"handoff_{int(time.time())}"
    client.post("/api/session/open", json={"user_id": uid3})
    show("写日记", client.post("/api/chat", json={"user_id": uid3, "message": "写日记"}))
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
    main()
