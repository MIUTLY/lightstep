"""请求 / 响应模型（Pydantic v2）。"""
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field, StrictBool, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
UserId = NonEmptyText


# ---------- 请求 ----------

class UserRequest(BaseModel):
    user_id: UserId


class ChatRequest(UserRequest):
    message: NonEmptyText


class ChooseTimeRequest(UserRequest):
    when: Literal["now", "later", "not_today"]


class CommitRequest(UserRequest):
    agree: StrictBool


class StepCompleteRequest(UserRequest):
    duration_ms: Annotated[int, Field(strict=True, ge=0)]


class StepResizeRequest(UserRequest):
    direction: Literal["smaller", "bigger"]


class ExitRequest(UserRequest):
    gentle: StrictBool = False


class NoteRequest(UserRequest):
    content: NonEmptyText


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
