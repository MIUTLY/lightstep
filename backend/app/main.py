"""FastAPI 应用入口（后端 API + 前端静态托管）。

后端 API 在 /api/* 下；前端页面在项目根目录 static/ 下，打开 http://127.0.0.1:8000 即可。
"""
import os
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from .llm import AIError

from . import services, memo
from .schemas import MemoCommand, FocusCaptureRequest
from .config import settings
from .schemas import (
    ChatRequest, ChooseTimeRequest, CommitRequest, ExitRequest,
    NoteRequest, StepCompleteRequest, StepResizeRequest,
    UserId, UserRequest, GenerateTaskRequest, GenerationRetryRequest, GenerationAnswerRequest,
)

app = FastAPI(title="轻步 LightStep", description="AI 学习搭子「小步」后端")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """进程存活检查；不表示真实模型已连通。"""
    return {"status": "ok", "storage": "sqlite", "receipt_storage": "client"}


@app.post("/api/session/open")
def open_session(req: UserRequest):
    current = memo.load(services.db, req.user_id)
    if current['days'] or current['active']:
        return memo.view(current)
    return services.handle_open(req.user_id)


@app.post("/api/chat")
def chat(req: ChatRequest):
    if req.workflow == 'legacy':
        if memo.load(services.db, req.user_id)['active']:
            raise HTTPException(409, '请先结束备忘录专注。')
        return services.handle_chat(req.user_id, req.message)
    if not req.request_id:
        raise HTTPException(422, '今日任务识别需要request_id，重试必须复用该ID。')
    return memo.execute(services.db, services.llm, req.user_id, req.request_id,
                        {'action':'chat','text':req.message})


@app.post("/api/reminders/poll", deprecated=True)
def poll_reminders(req: UserRequest):
    return services.poll_start_reminder(req.user_id)


@app.exception_handler(AIError)
async def ai_error_handler(request, error):
    # Existing frontend displays a string detail. Task generation itself returns a Reply with draft status.
    return JSONResponse(status_code=error.status, content={"detail": error.message, "code": error.code, "retryable": True})


@app.post("/api/task/generate")
def generate_task(req: GenerateTaskRequest):
    return services._create_task(req.user_id, req.goal)


@app.get("/api/task/generation")
def generation_status(user_id: UserId):
    return {"generation": services.generation_status(user_id)}


@app.post("/api/task/generation/retry")
def retry_generation(req: GenerationRetryRequest):
    return services.retry_generation(req.user_id, req.generation_id)


@app.post("/api/task/generation/answer")
def answer_generation(req: GenerationAnswerRequest):
    return services.retry_generation(req.user_id, req.generation_id, req.answer)


@app.post("/api/task/choose_time")
def choose_time(req: ChooseTimeRequest):
    return services.handle_choose_time(req.user_id, req.when)


@app.post("/api/task/commit")
def commit(req: CommitRequest):
    return services.handle_commit(req.user_id, req.agree)


@app.post("/api/step/complete")
def step_complete(req: StepCompleteRequest):
    return services.handle_step_complete(req.user_id, req.duration_ms, req.step_id)


@app.post("/api/step/resize")
def step_resize(req: StepResizeRequest):
    return services.handle_resize(req.user_id, req.direction, req.step_id)


@app.post("/api/task/exit")
def exit_task(req: ExitRequest):
    return services.handle_exit(req.user_id, req.gentle)


@app.post("/api/note")
def note(req: NoteRequest):
    return services.handle_note(req.user_id, req.content)


@app.post("/api/handoff/resume")
def handoff_resume(req: UserRequest):
    return services.resume_handoff(req.user_id)


@app.post("/api/handoff/dismiss")
def handoff_dismiss(req: UserRequest):
    return services.dismiss_handoff(req.user_id)


@app.get("/api/journal", deprecated=True)
@app.post("/api/journal/add", deprecated=True)
@app.delete("/api/journal/{entry_id}", deprecated=True)
def journal_retired():
    # 不解析或保存回执留言；旧客户端明确得到迁移提示。
    raise HTTPException(status_code=410, detail={
        "code": "JOURNAL_CLIENT_ONLY",
        "message": "回执与手帐由客户端本地保存，此服务端接口已停用。",
    })


@app.get("/api/session/state")
def session_state(user_id: UserId):
    current = memo.load(services.db,user_id)
    if current['days'] or current['active']:
        return memo.view(current)
    return services.get_state(user_id)


@app.get("/api/history")
def history(user_id: UserId):
    return services.get_history(user_id)


@app.get("/api/daily/summary")
def daily_summary(user_id: UserId):
    return services.get_daily_summary(user_id)


@app.post('/api/focus/capture')
def focus_capture(req: FocusCaptureRequest):
    if req.answer and req.anchor_id:
        raise HTTPException(422, '请提供文字回答或选择一个位置，不要同时提供。')
    try:
        return memo.execute(services.db,services.llm,req.user_id,req.request_id,
                            req.model_dump(exclude={'user_id','request_id'},exclude_none=True))
    except sqlite3.Error:
        raise HTTPException(503, '暂时无法保存新增任务，请保留输入并使用原request_id重试。') from None


@app.get('/api/today')
def today_memo(user_id: UserId, date: str | None = None):
    return memo.view(memo.load(services.db,user_id),date)


@app.get('/api/today/operations')
def memo_operations(user_id: UserId):
    with services.db._conn() as c:
        rows = c.execute('SELECT request_id FROM memo_operations WHERE user_id=? ORDER BY rowid DESC LIMIT 50', (user_id,)).fetchall()
    return [memo.operation(services.db,user_id,r[0]) for r in rows]


@app.get('/api/today/operation')
def memo_operation(user_id: UserId, request_id: UserId):
    return memo.operation(services.db,user_id,request_id)


@app.post('/api/today/command')
def memo_command(req: MemoCommand):
    if req.action == 'select' and services.db.get_active_task(req.user_id):
        raise HTTPException(409, '仍有旧版任务，请先在旧流程结束它；旧数据已保留。')
    return memo.execute(services.db,services.llm,req.user_id,req.request_id,
                        req.model_dump(exclude={'user_id','request_id'},exclude_none=True))


# 前端静态资源（必须在所有 API 路由之后挂载，否则会抢走 /api 路径）
_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if settings.serve_debug_ui:
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
