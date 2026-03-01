"""Schedules router — CRUD for user cron schedules."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.core.cron import cron_to_human, validate_cron_expression
from angie.db.session import get_session
from angie.models.schedule import ScheduledJob
from angie.models.user import User

router = APIRouter()


# ------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    cron_expression: str = Field(max_length=50)
    agent_slug: str | None = None
    task_payload: dict | None = None
    is_enabled: bool = True
    next_run_at: datetime | None = None
    conversation_id: str | None = None


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    cron_expression: str | None = Field(default=None, max_length=50)
    agent_slug: str | None = None
    task_payload: dict | None = None
    is_enabled: bool | None = None
    next_run_at: datetime | None = None


class ScheduleOut(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None
    cron_expression: str
    cron_human: str
    agent_slug: str | None
    task_payload: dict
    is_enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _to_out(job: ScheduledJob) -> ScheduleOut:
    return ScheduleOut(
        id=job.id,
        user_id=job.user_id,
        name=job.name,
        description=job.description,
        cron_expression=job.cron_expression,
        cron_human=cron_to_human(job.cron_expression),
        agent_slug=job.agent_slug,
        task_payload=job.task_payload or {},
        is_enabled=job.is_enabled,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/", response_model=list[ScheduleOut])
async def list_schedules(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ScheduledJob).where(ScheduledJob.user_id == user.id).order_by(ScheduledJob.name)
    )
    return [_to_out(j) for j in result.scalars().all()]


@router.post("/", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    valid, err = validate_cron_expression(body.cron_expression)
    if not valid:
        raise HTTPException(status_code=422, detail=err)

    is_once = body.cron_expression.strip() == "@once"
    if is_once and body.next_run_at is None:
        raise HTTPException(
            status_code=422,
            detail="next_run_at is required for @once schedules",
        )
    if is_once and body.next_run_at is not None:
        # Normalise to UTC-aware for comparison regardless of whether the client
        # sent a naive or tz-aware timestamp.
        nra = body.next_run_at
        if nra.tzinfo is None:
            nra = nra.replace(tzinfo=UTC)
        if nra <= datetime.now(UTC):
            raise HTTPException(
                status_code=422,
                detail="next_run_at must be a future timestamp for @once schedules",
            )

    job = ScheduledJob(
        user_id=user.id,
        name=body.name,
        description=body.description,
        cron_expression=body.cron_expression,
        agent_slug=body.agent_slug,
        task_payload=body.task_payload or {},
        is_enabled=body.is_enabled,
        next_run_at=body.next_run_at if is_once else None,
        conversation_id=body.conversation_id,
    )
    session.add(job)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A schedule named '{body.name}' already exists",
        ) from exc
    await session.refresh(job)
    return _to_out(job)


@router.get("/{schedule_id}", response_model=ScheduleOut)
async def get_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(ScheduledJob, schedule_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _to_out(job)


@router.patch("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(ScheduledJob, schedule_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updates = body.model_dump(exclude_unset=True)
    if "cron_expression" in updates:
        valid, err = validate_cron_expression(updates["cron_expression"])
        if not valid:
            raise HTTPException(status_code=422, detail=err)

    # Determine the effective cron expression after applying updates
    effective_expr = updates.get("cron_expression", job.cron_expression)
    if effective_expr.strip() == "@once":
        # next_run_at must be provided either in this update or already on the job
        effective_next_run = updates.get("next_run_at", job.next_run_at)
        if effective_next_run is None:
            raise HTTPException(
                status_code=422,
                detail="next_run_at is required for @once schedules",
            )
        # When next_run_at is being explicitly set (or already set), ensure it
        # is in the future so the job won't be immediately disabled on registration.
        if "next_run_at" in updates and effective_next_run is not None:
            nra = effective_next_run
            if nra.tzinfo is None:
                nra = nra.replace(tzinfo=UTC)
            if nra <= datetime.now(UTC):
                raise HTTPException(
                    status_code=422,
                    detail="next_run_at must be a future timestamp for @once schedules",
                )

    for k, v in updates.items():
        setattr(job, k, v)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        conflicting_name = updates.get("name") or job.name
        raise HTTPException(
            status_code=409,
            detail=f"A schedule named '{conflicting_name}' already exists",
        ) from exc
    await session.refresh(job)
    return _to_out(job)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(ScheduledJob, schedule_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await session.delete(job)


@router.patch("/{schedule_id}/toggle", response_model=ScheduleOut)
async def toggle_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(ScheduledJob, schedule_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    job.is_enabled = not job.is_enabled
    await session.flush()
    await session.refresh(job)
    return _to_out(job)
