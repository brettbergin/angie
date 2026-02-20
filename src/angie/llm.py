"""LLM factory — returns a configured pydantic-ai model.

Priority:
  1. GitHub Copilot (GITHUB_TOKEN set) — uses OpenAI-compatible endpoint
  2. OpenAI (OPENAI_API_KEY set)
  3. Raises RuntimeError if neither is configured
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)

_model_cache: "Model | None" = None


def get_llm_model(*, force_refresh: bool = False) -> "Model":
    """Return a cached pydantic-ai model instance."""
    global _model_cache
    if _model_cache is not None and not force_refresh:
        return _model_cache
    _model_cache = _build_model()
    return _model_cache


def _build_model() -> "Model":
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from angie.config import get_settings

    settings = get_settings()

    if settings.github_token:
        logger.info("LLM: using GitHub Copilot endpoint (%s)", settings.copilot_api_base)
        provider = OpenAIProvider(
            base_url=settings.copilot_api_base,
            api_key=settings.github_token,
        )
        return OpenAIModel(settings.copilot_model, provider=provider)

    if settings.openai_api_key:
        logger.info("LLM: using OpenAI (model=%s)", settings.copilot_model)
        provider = OpenAIProvider(api_key=settings.openai_api_key)
        return OpenAIModel(settings.copilot_model, provider=provider)

    raise RuntimeError(
        "No LLM configured. Set GITHUB_TOKEN (GitHub Copilot) "
        "or OPENAI_API_KEY (OpenAI) in your .env file."
    )


def is_llm_configured() -> bool:
    """Return True if at least one LLM provider is configured."""
    from angie.config import get_settings

    s = get_settings()
    return bool(s.github_token or s.openai_api_key)
