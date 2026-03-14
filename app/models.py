from datetime import date, datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    subject: str = "General"
    due_date: Optional[date] = None
    is_done: bool = False

    owner_id: int = Field(foreign_key="user.id", index=True)

    importance: int = 3
    estimated_minutes: int | None = None


# ----------------------------
# Persisted daily plan tables
# ----------------------------
class DayPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    owner_id: int = Field(foreign_key="user.id", index=True)
    plan_date: date = Field(index=True)

    minutes_budget: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    items: list["DayPlanItem"] = Relationship(back_populates="plan")


class DayPlanItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    plan_id: int = Field(foreign_key="dayplan.id", index=True)
    task_id: int = Field(foreign_key="task.id", index=True)

    order_index: int = 0
    minutes: int = 0

    plan: Optional[DayPlan] = Relationship(back_populates="items")