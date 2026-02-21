"""WebSocket chat endpoint — real LLM responses via pydantic-ai."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from jose import JWTError, jwt

from angie.channels.web_chat import WebChatChannel
from angie.config import get_settings

router = APIRouter()
_web_channel = WebChatChannel()
logger = logging.getLogger(__name__)


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

    # Build system prompt and agent once per connection
    from angie.core.prompts import get_prompt_manager
    from angie.llm import get_llm_model, is_llm_configured

    pm = get_prompt_manager()
    system_prompt = pm.compose_for_user(user_id)

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
