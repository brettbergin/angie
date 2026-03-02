"""Token usage recording and cost estimation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Pricing per 1M tokens: (input_cost, output_cost)
# Updated as of 2025 pricing
MODEL_PRICING: dict[tuple[str, str], tuple[float, float]] = {
    # OpenAI
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("openai", "gpt-4-turbo"): (10.00, 30.00),
    ("openai", "gpt-4"): (30.00, 60.00),
    ("openai", "gpt-3.5-turbo"): (0.50, 1.50),
    ("openai", "o1"): (15.00, 60.00),
    ("openai", "o1-mini"): (3.00, 12.00),
    ("openai", "o3-mini"): (1.10, 4.40),
    # GitHub Models (uses OpenAI models, same pricing)
    ("github", "openai/gpt-4o"): (2.50, 10.00),
    ("github", "openai/gpt-4o-mini"): (0.15, 0.60),
    ("github", "gpt-4o"): (2.50, 10.00),
    ("github", "gpt-4o-mini"): (0.15, 0.60),
    # Anthropic
    ("anthropic", "claude-sonnet-4"): (3.00, 15.00),
    ("anthropic", "claude-opus-4"): (15.00, 75.00),
    ("anthropic", "claude-haiku-4"): (0.80, 4.00),
    ("anthropic", "claude-3-5-sonnet"): (3.00, 15.00),
    ("anthropic", "claude-3-5-haiku"): (0.80, 4.00),
    ("anthropic", "claude-3-opus"): (15.00, 75.00),
}


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a given usage.

    Tries exact (provider, model) match first, then prefix matching.
    Returns 0.0 for unknown models.
    """
    provider = provider.lower()
    model = model.lower()

    # Exact match
    key = (provider, model)
    if key in MODEL_PRICING:
        input_price, output_price = MODEL_PRICING[key]
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    # Prefix match: e.g. "gpt-4o-2024-08-06" matches "gpt-4o"
    for (p, m), (input_price, output_price) in MODEL_PRICING.items():
        if p == provider and model.startswith(m):
            return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    return 0.0


def _get_provider_and_model() -> tuple[str, str]:
    """Read current provider and model from settings."""
    from angie.config import get_settings

    settings = get_settings()
    provider = settings.llm_provider
    if provider == "anthropic":
        return provider, settings.anthropic_model
    return provider, settings.copilot_model


async def record_usage(
    *,
    user_id: str | None,
    agent_slug: str | None,
    usage: Any,
    source: str,
    task_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """Persist a TokenUsage record to the database.

    ``usage`` should be a pydantic-ai ``Usage`` object with ``input_tokens``,
    ``output_tokens``, ``total_tokens``, ``request_count``, and ``model_name`` attrs.
    Failures are logged but never propagated.
    """
    try:
        from angie.db.session import get_session_factory
        from angie.models.token_usage import TokenUsage

        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or 0
        request_count = getattr(usage, "requests", 0) or 0

        # pydantic-ai Usage doesn't expose tool_call_count directly
        tool_call_count = 0

        provider, model = _get_provider_and_model()
        cost = estimate_cost(provider, model, input_tokens, output_tokens)

        async with get_session_factory()() as session:
            record = TokenUsage(
                user_id=user_id,
                agent_slug=agent_slug,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                request_count=request_count,
                tool_call_count=tool_call_count,
                estimated_cost_usd=cost,
                source=source,
                task_id=task_id,
                conversation_id=conversation_id,
            )
            session.add(record)
            await session.commit()

        logger.debug(
            "Recorded token usage: source=%s agent=%s tokens=%d cost=$%.6f",
            source,
            agent_slug,
            total_tokens,
            cost,
        )
    except Exception:
        logger.warning("Failed to record token usage", exc_info=True)


def record_usage_fire_and_forget(**kwargs: Any) -> None:
    """Schedule record_usage without blocking the caller.

    Uses asyncio.create_task() when an event loop is running (async context),
    falls back to asyncio.run() for sync contexts (e.g. Celery workers).
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(record_usage(**kwargs))
    except RuntimeError:
        # No running event loop — run synchronously
        try:
            asyncio.run(record_usage(**kwargs))
        except Exception:
            logger.warning("Failed to record token usage (sync fallback)", exc_info=True)
