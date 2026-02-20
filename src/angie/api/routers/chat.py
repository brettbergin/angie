"""WebSocket chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from angie.channels.web_chat import WebChatChannel

router = APIRouter()

_web_channel = WebChatChannel()


@router.websocket("/ws/{user_id}")
async def chat_ws(websocket: WebSocket, user_id: str):
    await websocket.accept()
    _web_channel.register_connection(user_id, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            # Emit as a USER_MESSAGE event into the Angie event loop
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
