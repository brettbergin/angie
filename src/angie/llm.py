"""LLM factory — returns a configured pydantic-ai model.

Priority:
  1. GitHub Models API (GITHUB_TOKEN set) — uses the OpenAI-compatible
     inference endpoint at models.inference.ai.azure.com
  2. OpenAI (OPENAI_API_KEY set)
  3. Raises RuntimeError if neither is configured
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.models import Model

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
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from angie.config import get_settings

    settings = get_settings()

    if settings.github_token:
        logger.info("LLM: using GitHub Models API (%s)", settings.github_models_api_base)
        provider = OpenAIProvider(
            base_url=settings.github_models_api_base,
            api_key=settings.github_token,
        )
        return OpenAIModel(settings.copilot_model, provider=provider), float("inf")

    if settings.openai_api_key:
        logger.info("LLM: using OpenAI (model=%s)", settings.copilot_model)
        provider = OpenAIProvider(api_key=settings.openai_api_key)
        return OpenAIModel(settings.copilot_model, provider=provider), float("inf")

    raise RuntimeError(
        "No LLM configured. Set GITHUB_TOKEN (GitHub Models) "
        "or OPENAI_API_KEY (OpenAI) in your .env file."
    )


def is_llm_configured() -> bool:
    """Return True if at least one LLM provider is configured."""
    from angie.config import get_settings

    s = get_settings()
    return bool(s.github_token or s.openai_api_key)
