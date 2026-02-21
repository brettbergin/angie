"""WebSocket chat endpoint — real LLM responses via pydantic-ai."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from jose import JWTError, jwt

from angie.channels.web_chat import WebChatChannel
from angie.config import get_settings

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


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, token: str):
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

    # Load user from DB for profile context and prompt lookup
    from angie.core.prompts import get_prompt_manager
    from angie.db.session import get_session_factory
    from angie.llm import get_llm_model, is_llm_configured
    from angie.models.user import User

    pm = get_prompt_manager()
    prompt_user_id = user_id
    user_context = ""

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                prompt_user_id = user.username
                user_context = _build_user_context(user)
    except Exception as exc:
        logger.warning("Could not load user profile for chat context: %s", exc)

    # Compose system prompt: SYSTEM > ANGIE > USER_PROMPTS
    # Try user-specific prompts first, fall back to "default"
    system_prompt = pm.compose_for_user(prompt_user_id)
    if not pm.get_user_prompts(prompt_user_id) and prompt_user_id != "default":
        system_prompt = pm.compose_for_user("default")

    # Inject user profile into the prompt
    if user_context:
        system_prompt = f"{system_prompt}\n\n---\n\n{user_context}"

    # Conversation history persists across messages in this WebSocket session
    message_history: list = []

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

            if agent is None:
                reply = "⚠️ No LLM configured. Set GITHUB_TOKEN or OPENAI_API_KEY in your .env."
            else:
                try:
                    result = await agent.run(
                        user_message,
                        message_history=message_history if message_history else None,
                    )
                    reply = str(result.output)
                    # Update history with the full conversation so far
                    message_history = result.all_messages()
                except Exception as exc:
                    logger.error("LLM error in chat: %s", exc)
                    reply = f"⚠️ Sorry, I ran into an error: {exc}"

            await websocket.send_text(json.dumps({"content": reply, "role": "assistant"}))

    except WebSocketDisconnect:
        _web_channel.unregister_connection(user_id)
