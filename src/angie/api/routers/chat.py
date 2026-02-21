"""WebSocket chat endpoint — real LLM responses via pydantic-ai."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from jose import JWTError, jwt
from sqlalchemy import func, select

from angie.channels.web_chat import WebChatChannel
from angie.config import get_settings
from angie.models.conversation import ChatMessage, Conversation, MessageRole

if TYPE_CHECKING:
    from angie.models.user import User

router = APIRouter()
_web_channel = WebChatChannel()
logger = logging.getLogger(__name__)


def _build_user_context(user: User) -> str:
    """Build a user profile block for injection into the system prompt."""
    parts = [f"## Current User\n- **Name**: {user.full_name or user.username}"]
    parts.append(f"- **Username**: {user.username}")
    parts.append(f"- **Email**: {user.email}")
    if user.timezone:
        parts.append(f"- **Timezone**: {user.timezone}")
    if user.preferred_channel:
        parts.append(f"- **Preferred Channel**: {user.preferred_channel}")
    return "\n".join(parts)


def _generate_title(text: str) -> str:
    """Generate a conversation title from the first user message."""
    title = text.strip().replace("\n", " ")
    if len(title) > 50:
        title = title[:47] + "..."
    return title


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, token: str, conversation_id: str | None = None):
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except JWTError as err:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from err

    await websocket.accept()
    _web_channel.register_connection(user_id, websocket)

    from angie.core.prompts import get_prompt_manager
    from angie.db.session import get_session_factory
    from angie.llm import get_llm_model, is_llm_configured
    from angie.models.user import User

    pm = get_prompt_manager()
    prompt_user_id = user_id
    user_context = ""
    session_factory = get_session_factory()

    try:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                prompt_user_id = user.username
                user_context = _build_user_context(user)
    except Exception as exc:
        logger.warning("Could not load user profile for chat context: %s", exc)

    # Compose system prompt: SYSTEM > ANGIE > USER_PROMPTS
    system_prompt = pm.compose_for_user(prompt_user_id)
    if not pm.get_user_prompts(prompt_user_id) and prompt_user_id != "default":
        system_prompt = pm.compose_for_user("default")

    if user_context:
        system_prompt = f"{system_prompt}\n\n---\n\n{user_context}"

    # If conversation_id provided, load existing message history from DB
    message_history: list = []
    is_first_message = True

    if conversation_id:
        try:
            async with session_factory() as session:
                convo = await session.get(Conversation, conversation_id)
                if convo and convo.user_id == user_id:
                    result = await session.execute(
                        select(ChatMessage)
                        .where(ChatMessage.conversation_id == conversation_id)
                        .order_by(ChatMessage.created_at.asc())
                    )
                    db_messages = result.scalars().all()
                    if db_messages:
                        is_first_message = False
        except Exception as exc:
            logger.warning("Could not load conversation history: %s", exc)

    agent = None
    if is_llm_configured():
        from pydantic_ai import Agent

        model = get_llm_model()
        agent = Agent(model=model, system_prompt=system_prompt)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                user_message = data.get("content", raw)
            except json.JSONDecodeError:
                user_message = raw

            # Create conversation on first message if none provided
            if not conversation_id:
                try:
                    async with session_factory() as session:
                        convo = Conversation(
                            user_id=user_id,
                            title=_generate_title(user_message),
                        )
                        session.add(convo)
                        await session.flush()
                        await session.refresh(convo)
                        conversation_id = convo.id
                        await session.commit()
                    is_first_message = False
                except Exception as exc:
                    logger.error("Failed to create conversation: %s", exc)

            # Auto-title on first message of an existing conversation
            if is_first_message and conversation_id:
                try:
                    async with session_factory() as session:
                        convo = await session.get(Conversation, conversation_id)
                        if convo and convo.title == "New Chat":
                            convo.title = _generate_title(user_message)
                            await session.commit()
                except Exception as exc:
                    logger.warning("Could not update conversation title: %s", exc)
                is_first_message = False

            # Persist user message
            if conversation_id:
                try:
                    async with session_factory() as session:
                        msg = ChatMessage(
                            conversation_id=conversation_id,
                            role=MessageRole.USER,
                            content=user_message,
                        )
                        session.add(msg)
                        await session.commit()
                except Exception as exc:
                    logger.warning("Could not persist user message: %s", exc)

            if agent is None:
                reply = "⚠️ No LLM configured. Set GITHUB_TOKEN or OPENAI_API_KEY in your .env."
            else:
                try:
                    result = await agent.run(
                        user_message,
                        message_history=message_history if message_history else None,
                    )
                    reply = str(result.output)
                    message_history = result.all_messages()
                except Exception as exc:
                    logger.error("LLM error in chat: %s", exc)
                    reply = f"⚠️ Sorry, I ran into an error: {exc}"

            # Persist assistant message
            if conversation_id:
                try:
                    async with session_factory() as session:
                        msg = ChatMessage(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=reply,
                        )
                        session.add(msg)
                        # Touch conversation updated_at
                        await session.execute(
                            select(Conversation).where(Conversation.id == conversation_id)
                        )
                        convo = await session.get(Conversation, conversation_id)
                        if convo:
                            convo.updated_at = func.now()
                        await session.commit()
                except Exception as exc:
                    logger.warning("Could not persist assistant message: %s", exc)

            response = {"content": reply, "role": "assistant"}
            if conversation_id:
                response["conversation_id"] = conversation_id
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        _web_channel.unregister_connection(user_id)
