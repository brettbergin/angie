"""Channel configs router — save/load per-user channel settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.channel import ChannelConfig, ChannelType
from angie.models.user import User

router = APIRouter()


class ChannelConfigIn(BaseModel):
    type: str
    is_enabled: bool = True
    config: dict = {}


class ChannelConfigOut(BaseModel):
    id: str
    type: str
    is_enabled: bool
    config: dict

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ChannelConfigOut])
async def list_channel_configs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ChannelConfig).where(ChannelConfig.user_id == current_user.id)
    )
    return result.scalars().all()


@router.put("/{channel_type}", response_model=ChannelConfigOut)
async def upsert_channel_config(
    channel_type: str,
    body: ChannelConfigIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create or update a channel config for the current user."""
    ct = ChannelType(channel_type)
    result = await session.execute(
        select(ChannelConfig).where(
            ChannelConfig.user_id == current_user.id,
            ChannelConfig.type == ct,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = ChannelConfig(user_id=current_user.id, type=ct)
        session.add(cfg)
    cfg.is_enabled = body.is_enabled
    cfg.config = body.config
    await session.flush()
    await session.refresh(cfg)
    return cfg
