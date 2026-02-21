"""WebSocket chat endpoint — real LLM responses via pydantic-ai."""

from __future__ import annotations

import json
import logging
import re
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


def _build_agents_catalog() -> str:
    """Build a prompt section listing all available agents and their capabilities."""
    from angie.agents.registry import get_registry

    registry = get_registry()
    agents = registry.list_all()
    if not agents:
        return ""

    lines = ["## Available Agents", ""]
    lines.append(
        "When the user asks you to perform a real-world action (not just answer a question), "
        "use the `dispatch_task` tool to route the work to the appropriate agent below. "
        "If the user is just making conversation or asking a question you can answer directly, "
        "respond normally without dispatching a task."
    )
    lines.append("")
    lines.append(
        "### @-Mentions\n"
        "Users can @-mention an agent by slug (e.g. `@spotify play some jazz`). "
        "When a message contains an @-mention, you MUST use that agent's slug as the "
        "`agent_slug` parameter in `dispatch_task`. Strip the @-mention from the intent text."
    )
    lines.append("")
    for agent in agents:
        caps = ", ".join(agent.capabilities) if agent.capabilities else "general"
        lines.append(f"- **{agent.name}** (`{agent.slug}`): {agent.description}")
        lines.append(f"  Capabilities: {caps}")
    return "\n".join(lines)


# Regex pattern to extract @agent-slug mentions from user messages
_MENTION_PATTERN = re.compile(r"@([a-z][a-z0-9_-]*)", re.IGNORECASE)


def _extract_mention(message: str) -> tuple[str | None, str]:
    """Extract @agent-slug from message. Returns (slug_or_none, cleaned_message)."""
    from angie.agents.registry import get_registry

    registry = get_registry()
    slugs = {a.slug for a in registry.list_all()}

    match = _MENTION_PATTERN.search(message)
    if match:
        slug = match.group(1).lower()
        if slug in slugs:
            cleaned = message[: match.start()] + message[match.end() :]
            return slug, cleaned.strip()
    return None, message


def _build_chat_agent(system_prompt: str, user_id: str, conversation_id_ref: list):
    """Build a pydantic-ai Agent with dispatch_task tool for the chat session."""
    from pydantic_ai import Agent

    from angie.llm import get_llm_model

    model = get_llm_model()
    agent: Agent[None, str] = Agent(model=model, system_prompt=system_prompt)

    @agent.tool_plain
    async def dispatch_task(
        title: str,
        intent: str,
        agent_slug: str = "",
        parameters: str = "{}",
    ) -> str:
        """Dispatch a task to an Angie agent for async execution.

        Use this tool when the user asks you to DO something that requires
        a real-world action (send email, control smart home, manage tasks,
        check calendar, etc.). Do NOT use this for questions you can answer
        directly through conversation.

        Args:
            title: Short descriptive title of the task (e.g. "Turn off living room lights")
            intent: Full natural-language description of what the user wants done
            agent_slug: The slug of the agent to handle this (e.g. "hue", "gmail").
                        Leave empty for auto-resolution.
            parameters: JSON string of extracted key-value parameters relevant to the task
        """
        from angie.core.intent import dispatch_task as do_dispatch

        try:
            params = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError:
            params = {}

        result = await do_dispatch(
            title=title,
            intent=intent,
            user_id=user_id,
            conversation_id=conversation_id_ref[0] if conversation_id_ref else None,
            agent_slug=agent_slug or None,
            parameters=params,
        )

        if result.get("dispatched"):
            return (
                f"Task dispatched successfully. Task ID: {result['task_id']}. "
                f"The {result.get('agent', 'appropriate')} agent will handle this. "
                "I'll update you here when it's done."
            )
        return f"Failed to dispatch task: {result.get('error', 'unknown error')}"

    return agent


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
    from angie.llm import is_llm_configured
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

    # Inject available agents catalog
    agents_catalog = _build_agents_catalog()
    if agents_catalog:
        system_prompt = f"{system_prompt}\n\n---\n\n{agents_catalog}"

    # If conversation_id provided, load existing message history from DB
    message_history: list = []
    is_first_message = True
    # Mutable ref so the tool closure can access the current conversation_id
    conversation_id_ref: list[str | None] = [conversation_id]

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
        agent = _build_chat_agent(system_prompt, user_id, conversation_id_ref)

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
                        conversation_id_ref[0] = convo.id
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

            # Extract @-mention if present
            mentioned_slug, cleaned_message = _extract_mention(user_message)
            llm_message = user_message
            if mentioned_slug:
                llm_message = (
                    f"[The user @-mentioned the `{mentioned_slug}` agent. "
                    f"Use agent_slug='{mentioned_slug}' when dispatching.]\n\n{cleaned_message}"
                )

            task_dispatched = False
            if agent is None:
                reply = "⚠️ No LLM configured. Set GITHUB_TOKEN or OPENAI_API_KEY in your .env."
            else:
                try:
                    result = await agent.run(
                        llm_message,
                        message_history=message_history if message_history else None,
                    )
                    reply = str(result.output)
                    message_history = result.all_messages()
                    # Check if dispatch_task was called by looking at tool calls
                    task_dispatched = any(
                        getattr(m, "part_kind", None) == "tool-call"
                        and getattr(m, "tool_name", None) == "dispatch_task"
                        for msg in result.all_messages()
                        for m in (getattr(msg, "parts", None) or [])
                    )
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
            if task_dispatched:
                response["task_dispatched"] = True
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        _web_channel.unregister_connection(user_id)
