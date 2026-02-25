"""LLM factory — returns a configured pydantic-ai model.

Supported providers (selected via LLM_PROVIDER env var):
  1. ``github``  — GitHub Models API (OpenAI-compatible endpoint)
  2. ``openai``  — OpenAI API
  3. ``anthropic`` — Anthropic Claude API
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from angie.config import Settings

logger = logging.getLogger(__name__)

_model_cache: Model | None = None
_model_expires_at: float = 0.0


def get_llm_model(*, force_refresh: bool = False) -> Model:
    """Return a cached pydantic-ai model instance."""
    global _model_cache, _model_expires_at
    if _model_cache is not None and not force_refresh and time.monotonic() < _model_expires_at:
        return _model_cache
    _model_cache, _model_expires_at = _build_model()
    return _model_cache


def _build_model() -> tuple[Model, float]:
    from angie.config import get_settings

    settings = get_settings()
    provider_name = settings.llm_provider

    if provider_name == "anthropic":
        return _build_anthropic(settings)
    if provider_name == "openai":
        return _build_openai(settings)
    # Default: github
    return _build_github(settings)


def _build_github(settings: Settings) -> tuple[Model, float]:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    if not settings.github_token:
        raise RuntimeError(
            "LLM_PROVIDER is 'github' but GITHUB_TOKEN is not set. "
            "Set GITHUB_TOKEN in your .env file."
        )
    logger.info("LLM: using GitHub Models API (%s)", settings.github_models_api_base)
    provider = OpenAIProvider(
        base_url=settings.github_models_api_base,
        api_key=settings.github_token,
    )
    return OpenAIChatModel(settings.copilot_model, provider=provider), float("inf")


def _build_openai(settings: Settings) -> tuple[Model, float]:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    if not settings.openai_api_key:
        raise RuntimeError(
            "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY in your .env file."
        )
    logger.info("LLM: using OpenAI (model=%s)", settings.copilot_model)
    provider = OpenAIProvider(api_key=settings.openai_api_key)
    return OpenAIChatModel(settings.copilot_model, provider=provider), float("inf")


def _build_anthropic(settings: Settings) -> tuple[Model, float]:
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    if not settings.anthropic_api_key:
        raise RuntimeError(
            "LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set. "
            "Set ANTHROPIC_API_KEY in your .env file."
        )
    logger.info("LLM: using Anthropic (model=%s)", settings.anthropic_model)
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    return AnthropicModel(settings.anthropic_model, provider=provider), float("inf")


def is_llm_configured() -> bool:
    """Return True if at least one LLM provider is configured."""
    from angie.config import get_settings

    s = get_settings()
    if s.llm_provider == "anthropic":
        return bool(s.anthropic_api_key)
    if s.llm_provider == "openai":
        return bool(s.openai_api_key)
    return bool(s.github_token)
