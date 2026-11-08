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
    workflow: Literal["today", "legacy"] = "today"
    request_id: Optional[NonEmptyText] = None


class GenerateTaskRequest(UserRequest):
    goal: NonEmptyText


class GenerationRetryRequest(UserRequest):
    generation_id: NonEmptyText


class GenerationAnswerRequest(GenerationRetryRequest):
    answer: NonEmptyText


class ChooseTimeRequest(UserRequest):
    when: Literal["now", "in_5_minutes", "in_10_minutes", "later", "not_today"]


class CommitRequest(UserRequest):
    agree: StrictBool


class StepCompleteRequest(UserRequest):
    duration_ms: Annotated[int, Field(strict=True, ge=0)] | None = Field(default=None, deprecated=True, description="兼容旧客户端；已停用，不参与任何进度或粒度判断")
    step_id: Optional[NonEmptyText] = None


class StepResizeRequest(UserRequest):
    direction: Literal["smaller", "bigger"]
    step_id: Optional[NonEmptyText] = None


class ExitRequest(UserRequest):
    gentle: StrictBool = False


class NoteRequest(UserRequest):
    content: NonEmptyText


# ---------- 响应 ----------

class TaskView(BaseModel):
    presentation: Optional[dict] = None
    title: str
    current_step: str
    steps_done: int
    granularity: str  # fine | normal | coarse
    state: str       # ready | committing | executing | done
    step_id: str = ""  # 当前显示动作的稳定标识，用于防止旧请求重复完成
    plan_format: str = "legacy"
    node_id: Optional[str] = None
    parent_id: Optional[str] = None
    remaining_leaf_ids: List[str] = []
    start_due_at: Optional[str] = Field(default=None, deprecated=True, description="计时已停用，恒为null")


class Reply(BaseModel):
    reply: str
    state: str
    buttons: List[str] = []
    task: Optional[TaskView] = None
    notes_to_recall: List[str] = []
    due_reminders: List[str] = Field(default_factory=list, deprecated=True, description="提醒已停用，恒为空列表")
    summary: Optional[str] = None
    generation: Optional[dict] = None


class DailySummary(BaseModel):
    date: str
    steps_done: int
    titles: List[str]


class HistoryItem(BaseModel):
    date: str
    title: str

class MemoBase(UserRequest):
    request_id: NonEmptyText
    model_config = {'extra': 'forbid'}

class MemoIntake(MemoBase):
    action: Literal['intake']
    text: NonEmptyText

class MemoReorder(MemoBase):
    action: Literal['reorder']
    date: Annotated[str, StringConstraints(pattern=r'^\d{4}-\d{2}-\d{2}$')]
    revision: Annotated[int, Field(strict=True, ge=0)]
    item_ids: List[NonEmptyText]

class MemoSelect(MemoBase):
    action: Literal['select']
    item_id: NonEmptyText
    answer: Optional[NonEmptyText] = None

class MemoStep(MemoBase):
    action: Literal['complete']
    session_id: NonEmptyText
    step_id: NonEmptyText

class MemoResize(MemoBase):
    action: Literal['resize']
    session_id: NonEmptyText
    step_id: NonEmptyText
    direction: Literal['smaller','bigger']

class MemoEnd(MemoBase):
    action: Literal['end']
    session_id: NonEmptyText

class MemoAck(MemoBase):
    action: Literal['ack']
    event_id: NonEmptyText

MemoCommand = Annotated[MemoIntake | MemoReorder | MemoSelect | MemoStep | MemoResize | MemoEnd | MemoAck, Field(discriminator='action')]


class FocusCaptureRequest(MemoBase):
    action: Literal['focus_capture'] = 'focus_capture'
    session_id: NonEmptyText
    text: NonEmptyText
    parent_request_id: Optional[NonEmptyText] = None
    answer: Optional[NonEmptyText] = None
    anchor_id: Optional[NonEmptyText] = None
