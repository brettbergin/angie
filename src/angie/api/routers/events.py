"""Events router — list and create."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.event import Event, EventType
from angie.models.user import User

router = APIRouter()


class EventCreate(BaseModel):
    type: str
    payload: dict = {}
    source_channel: str | None = None


class EventOut(BaseModel):
    id: str
    type: str
    source_channel: str | None
    user_id: str | None
    payload: dict
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[EventOut])
async def list_events(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Event)
        .where(Event.user_id == current_user.id)
        .order_by(Event.created_at.desc())
        .limit(200)
    )
    return result.scalars().all()


@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    event = Event(
        type=EventType(body.type),
        payload=body.payload,
        source_channel=body.source_channel,
        user_id=current_user.id,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event
