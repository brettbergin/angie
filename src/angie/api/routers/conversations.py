"""Conversations router — CRUD for conversations and messages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.conversation import ChatMessage, Conversation
from angie.models.user import User

router = APIRouter()


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str


class ConversationOut(BaseModel):
    id: str
    title: str
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


class ChatMessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kw):
        data = super().model_validate(obj, **kw)
        if hasattr(obj, "created_at") and obj.created_at:
            data.created_at = obj.created_at.isoformat()
        return data


@router.get("/", response_model=list[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = Conversation(
        user_id=current_user.id,
        title=body.title or "New Chat",
    )
    session.add(convo)
    await session.flush()
    await session.refresh(convo)
    return convo


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.get(Conversation, conversation_id)
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageOut])
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.get(Conversation, conversation_id)
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.get(Conversation, conversation_id)
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    convo.title = body.title
    await session.flush()
    await session.refresh(convo)
    return convo


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .options(selectinload(Conversation.messages))
    )
    convo = convo.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.delete(convo)
