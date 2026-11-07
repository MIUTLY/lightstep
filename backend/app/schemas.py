"""请求 / 响应模型（Pydantic v2）。"""
from typing import List, Optional

from pydantic import BaseModel


# ---------- 请求 ----------

class UserRequest(BaseModel):
    user_id: str


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChooseTimeRequest(BaseModel):
    user_id: str
    when: str  # "now" | "later" | "not_today"


class CommitRequest(BaseModel):
    user_id: str
    agree: bool


class StepCompleteRequest(BaseModel):
    user_id: str
    duration_ms: int  # 这一小步实际耗时（毫秒）


class StepResizeRequest(BaseModel):
    user_id: str
    direction: str  # "smaller"（太重了，拆细）| "bigger"（太简单了，加量）


class ExitRequest(BaseModel):
    user_id: str
    gentle: bool = False


class NoteRequest(BaseModel):
    user_id: str
    content: str


class JournalAddRequest(BaseModel):
    user_id: str
    note: str = ""


# ---------- 响应 ----------

class TaskView(BaseModel):
    title: str
    current_step: str
    steps_done: int
    granularity: str  # fine | normal | coarse
    state: str       # ready | committing | executing | done


class Reply(BaseModel):
    reply: str
    state: str
    buttons: List[str] = []
    task: Optional[TaskView] = None
    notes_to_recall: List[str] = []
    due_reminders: List[str] = []
    summary: Optional[str] = None


class DailySummary(BaseModel):
    date: str
    steps_done: int
    titles: List[str]


class HistoryItem(BaseModel):
    date: str
    title: str


class JournalEntry(BaseModel):
    id: int
    date: str
    steps_done: int
    titles: List[str]
    note: str
    created_at: str
