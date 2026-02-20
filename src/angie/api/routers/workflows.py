"""Workflows router — CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.user import User
from angie.models.workflow import Workflow

router = APIRouter()


class WorkflowCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    team_id: str | None = None
    trigger_event: str | None = None
    is_enabled: bool = True


class WorkflowOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    team_id: str | None
    trigger_event: str | None
    is_enabled: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[WorkflowOut])
async def list_workflows(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Workflow).order_by(Workflow.name))
    return result.scalars().all()


@router.post("/", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = Workflow(**body.model_dump())
    session.add(wf)
    await session.flush()
    await session.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: str,
    body: dict,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for k, v in body.items():
        if hasattr(wf, k):
            setattr(wf, k, v)
    await session.flush()
    await session.refresh(wf)
    return wf


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await session.delete(wf)
