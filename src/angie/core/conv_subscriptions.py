"""Conversation subscription system — tracks which agents are active in a conversation."""

from __future__ import annotations

import logging

from angie.cache.redis import get_redis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "angie:conv_subs"
_COOLDOWN_PREFIX = "angie:auto_cooldown"
_SUB_TTL = 86400  # 24 hours
_COOLDOWN_TTL = 30  # 30 seconds
_MAX_SUBS_PER_CONVERSATION = 5


async def subscribe_agent(conversation_id: str, agent_slug: str) -> bool:
    """Add an agent to a conversation's subscriber set.

    Returns True if the agent was added, False if the cap was reached.
    """
    key = f"{_KEY_PREFIX}:{conversation_id}"
    try:
        client = get_redis()
        current_size = await client.scard(key)
        if current_size >= _MAX_SUBS_PER_CONVERSATION:
            # Check if already subscribed (doesn't count against cap)
            if await client.sismember(key, agent_slug):
                return True
            logger.debug(
                "Subscription cap reached for conversation %s (%d/%d)",
                conversation_id,
                current_size,
                _MAX_SUBS_PER_CONVERSATION,
            )
            return False
        await client.sadd(key, agent_slug)
        await client.expire(key, _SUB_TTL)
        return True
    except Exception as exc:
        logger.warning(
            "Failed to subscribe agent %s to conversation %s: %s", agent_slug, conversation_id, exc
        )
        return False


async def unsubscribe_agent(conversation_id: str, agent_slug: str) -> None:
    """Remove an agent from a conversation's subscriber set."""
    key = f"{_KEY_PREFIX}:{conversation_id}"
    try:
        client = get_redis()
        await client.srem(key, agent_slug)
    except Exception as exc:
        logger.warning("Failed to unsubscribe agent %s: %s", agent_slug, exc)


async def get_subscribed_agents(conversation_id: str) -> set[str]:
    """Return the set of agent slugs subscribed to a conversation."""
    key = f"{_KEY_PREFIX}:{conversation_id}"
    try:
        client = get_redis()
        return await client.smembers(key)
    except Exception as exc:
        logger.warning("Failed to get subscribed agents: %s", exc)
        return set()


async def check_cooldown(conversation_id: str, agent_slug: str) -> bool:
    """Check if an agent is in cooldown for auto-responses in a conversation.

    Returns True if the agent is in cooldown (should NOT respond).
    """
    key = f"{_COOLDOWN_PREFIX}:{conversation_id}:{agent_slug}"
    try:
        client = get_redis()
        return await client.exists(key) > 0
    except Exception as exc:
        logger.warning("Failed to check cooldown: %s", exc)
        return True  # Fail safe: assume cooldown


async def set_cooldown(conversation_id: str, agent_slug: str) -> None:
    """Set a cooldown for an agent's auto-responses in a conversation."""
    key = f"{_COOLDOWN_PREFIX}:{conversation_id}:{agent_slug}"
    try:
        client = get_redis()
        await client.setex(key, _COOLDOWN_TTL, "1")
    except Exception as exc:
        logger.warning("Failed to set cooldown: %s", exc)
