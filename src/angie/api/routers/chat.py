"""WebSocket chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from jose import JWTError, jwt

from angie.channels.web_chat import WebChatChannel
from angie.config import get_settings

router = APIRouter()
_web_channel = WebChatChannel()


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, token: str):
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except JWTError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    await websocket.accept()
    _web_channel.register_connection(user_id, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            from angie.core.events import AngieEvent
            from angie.core.events import router as event_router
            from angie.models.event import EventType

            event = AngieEvent(
                type=EventType.USER_MESSAGE,
                user_id=user_id,
                payload={"message": text},
                source_channel="web",
            )
            await event_router.dispatch(event)
    except WebSocketDisconnect:
        _web_channel.unregister_connection(user_id)
