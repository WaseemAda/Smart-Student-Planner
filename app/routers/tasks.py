from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from jose import jwt, JWTError

from app.db import get_session
from app.models import Task, User, DayPlan, DayPlanItem
from app.schemas import (
    TaskCreate,
    TaskRead,
    PlanSaveRequest,
    PlanResponse,
    NextTaskResponse,
)
from app.core.security import SECRET_KEY, ALGORITHM


router = APIRouter(prefix="/tasks", tags=["tasks"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ----------------------------
# Smart helpers (backend)
# ----------------------------
def _days_until(d: Optional[date]) -> int:
    if d is None:
        return 10**9  # infinity-ish
    return (d - date.today()).days


def _urgency_score(d: Optional[date]) -> int:
    du = _days_until(d)
    if du >= 10**8:
        return 1          # no due date
    if du < 0:
        return 25         # overdue
    if du == 0:
        return 20         # today
    if du <= 2:
        return 16         # next 2 days
    if du <= 7:
        return 10         # this week
    if du <= 14:
        return 6          # next 2 weeks
    return 3              # later


def _smart_score(t: Task) -> int:
    if t.is_done:
        return -999999
    imp = int(t.importance or 3)
    return _urgency_score(t.due_date) * imp


def _task_minutes(t: Task) -> int:
    return int(t.estimated_minutes or 60)


# ----------------------------
# Tasks
# ----------------------------
@router.get("", response_model=list[TaskRead])
def list_tasks(
    sort: Literal["smart", "newest", "due"] = "smart",
    status: Literal["all", "active", "done"] = "all",
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    tasks = session.exec(select(Task).where(Task.owner_id == user.id)).all()

    # filter
    if status == "active":
        tasks = [t for t in tasks if not t.is_done]
    elif status == "done":
        tasks = [t for t in tasks if t.is_done]

    # sort
    if sort == "newest":
        tasks.sort(key=lambda t: t.id or 0, reverse=True)
    elif sort == "due":
        tasks.sort(key=lambda t: _days_until(t.due_date))
    else:  # smart
        tasks.sort(key=_smart_score, reverse=True)

    return tasks


@router.post("", response_model=TaskRead)
def create_task(
    task_in: TaskCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = Task(
        title=task_in.title,
        subject=task_in.subject,
        due_date=task_in.due_date,
        owner_id=user.id,
        importance=task_in.importance,
        estimated_minutes=task_in.estimated_minutes,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.post("/{task_id}/done", response_model=TaskRead)
def mark_done(
    task_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = session.get(Task, task_id)
    if not task or task.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_done = True
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = session.get(Task, task_id)
    if not task or task.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(task)
    session.commit()
    return {"ok": True}


# ----------------------------
# Persisted planning
# ----------------------------
@router.post("/plan/save", response_model=PlanResponse)
def save_today_plan(
    body: PlanSaveRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()

    # active tasks only
    tasks = session.exec(select(Task).where(Task.owner_id == user.id)).all()
    tasks = [t for t in tasks if not t.is_done]

    # greedy by (score per minute)
    candidates = sorted(
        tasks,
        key=lambda t: _smart_score(t) / max(_task_minutes(t), 1),
        reverse=True
    )

    remaining = body.minutes_budget
    picked: list[Task] = []

    for t in candidates:
        m = _task_minutes(t)
        if m <= remaining:
            picked.append(t)
            remaining -= m

    picked.sort(key=_smart_score, reverse=True)
    used = body.minutes_budget - remaining

    # overwrite today's plan if exists
    plan = session.exec(
        select(DayPlan).where(DayPlan.owner_id == user.id, DayPlan.plan_date == today)
    ).first()

    if plan:
        # delete old items
        old_items = session.exec(select(DayPlanItem).where(DayPlanItem.plan_id == plan.id)).all()
        for it in old_items:
            session.delete(it)
        plan.minutes_budget = body.minutes_budget
        session.add(plan)
        session.commit()
    else:
        plan = DayPlan(owner_id=user.id, plan_date=today, minutes_budget=body.minutes_budget)
        session.add(plan)
        session.commit()
        session.refresh(plan)

    # insert items
    for idx, t in enumerate(picked):
        session.add(
            DayPlanItem(
                plan_id=plan.id,
                task_id=t.id,
                order_index=idx,
                minutes=_task_minutes(t),
            )
        )

    session.commit()

    return PlanResponse(
        plan_date=today,
        minutes_budget=body.minutes_budget,
        used_minutes=used,
        remaining_minutes=remaining,
        tasks=[TaskRead.model_validate(t) for t in picked],
    )


@router.get("/plan/today", response_model=PlanResponse)
def get_today_plan(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()

    plan = session.exec(
        select(DayPlan).where(DayPlan.owner_id == user.id, DayPlan.plan_date == today)
    ).first()

    if not plan:
        return PlanResponse(
            plan_date=today,
            minutes_budget=0,
            used_minutes=0,
            remaining_minutes=0,
            tasks=[],
        )

    items = session.exec(
        select(DayPlanItem)
        .where(DayPlanItem.plan_id == plan.id)
        .order_by(DayPlanItem.order_index)
    ).all()

    tasks: list[Task] = []
    used = 0

    for it in items:
        t = session.get(Task, it.task_id)
        if t and t.owner_id == user.id and not t.is_done:
            tasks.append(t)
            used += int(it.minutes or _task_minutes(t))

    remaining = max(0, int(plan.minutes_budget) - used)

    return PlanResponse(
        plan_date=today,
        minutes_budget=int(plan.minutes_budget),
        used_minutes=used,
        remaining_minutes=remaining,
        tasks=[TaskRead.model_validate(t) for t in tasks],
    )


# ----------------------------
# “What should I do now?”
# ----------------------------
@router.get("/next", response_model=NextTaskResponse)
def what_should_i_do_now(
    max_minutes: int = 120,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    tasks = session.exec(select(Task).where(Task.owner_id == user.id)).all()
    tasks = [t for t in tasks if not t.is_done]

    if not tasks:
        return NextTaskResponse(task=None, reason="No active tasks.")

    def fits(t: Task) -> bool:
        return _task_minutes(t) <= max_minutes

    fitting = [t for t in tasks if fits(t)]
    pool = fitting if fitting else tasks

    best = max(pool, key=lambda t: (_smart_score(t), -_task_minutes(t)))

    du = _days_until(best.due_date)
    urgency_text = (
        "overdue" if du < 0 else
        "due today" if du == 0 else
        "due tomorrow" if du == 1 else
        f"due in {du} days" if du < 10**8 else
        "no due date"
    )

    reason = (
        f"Picked because it has high smart priority ({_smart_score(best)}), "
        f"is {urgency_text}, importance {best.importance}, ~{_task_minutes(best)} min."
    )

    return NextTaskResponse(task=TaskRead.model_validate(best), reason=reason)