"""Tasks router — CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.task import Task, TaskStatus
from angie.models.user import User

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    input_data: dict = {}
    source_channel: str | None = None


class TaskOut(BaseModel):
    id: str
    title: str
    status: str
    input_data: dict
    output_data: dict
    error: str | None
    source_channel: str | None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kw):
        data = super().model_validate(obj, **kw)
        if hasattr(obj, "created_at") and obj.created_at:
            data.created_at = obj.created_at.isoformat()
        if hasattr(obj, "updated_at") and obj.updated_at:
            data.updated_at = obj.updated_at.isoformat()
        return data


@router.get("/", response_model=list[TaskOut])
async def list_tasks(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Task).where(Task.user_id == current_user.id).order_by(Task.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = Task(
        user_id=current_user.id,
        title=body.title,
        input_data=body.input_data,
        source_channel=body.source_channel,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task_status(
    task_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if "status" in body:
        task.status = TaskStatus(body["status"])
    if "output_data" in body:
        task.output_data = body["output_data"]
    await session.flush()
    await session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    await session.delete(task)
