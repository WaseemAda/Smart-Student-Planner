from datetime import date
from pydantic import BaseModel, constr, Field


class TaskCreate(BaseModel):
    title: str
    subject: str = "General"
    due_date: date | None = None

    importance: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


class TaskRead(BaseModel):
    id: int
    title: str
    subject: str
    due_date: date | None
    is_done: bool

    importance: int
    estimated_minutes: int | None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: constr(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ----------------------------
# Planning + Recommendation
# ----------------------------
class PlanSaveRequest(BaseModel):
    minutes_budget: int = Field(ge=10, le=1440)


class PlanResponse(BaseModel):
    plan_date: date
    minutes_budget: int
    used_minutes: int
    remaining_minutes: int
    tasks: list[TaskRead]


class NextTaskResponse(BaseModel):
    task: TaskRead | None
    reason: str