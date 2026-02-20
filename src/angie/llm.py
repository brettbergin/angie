"""LLM factory — returns a configured pydantic-ai model.

Priority:
  1. GitHub Copilot (GITHUB_TOKEN set) — exchanges for a short-lived Copilot token,
     then uses the OpenAI-compatible endpoint
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

_COPILOT_TOKEN_TTL = 25 * 60  # refresh 5 min before the 30-min Copilot token expiry

_model_cache: Model | None = None
_model_expires_at: float = 0.0


def get_llm_model(*, force_refresh: bool = False) -> Model:
    """Return a cached pydantic-ai model instance, refreshing when the token is near expiry."""
    global _model_cache, _model_expires_at
    if _model_cache is not None and not force_refresh and time.monotonic() < _model_expires_at:
        return _model_cache
    _model_cache, _model_expires_at = _build_model()
    return _model_cache


def _exchange_copilot_token(github_token: str) -> tuple[str, float]:
    """Exchange a GitHub token for a short-lived Copilot session token.

    Returns the Copilot token and a monotonic expiry timestamp.
    """
    import httpx

    response = httpx.get(
        "https://api.github.com/copilot_internal/v2/token",
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/json",
        },
        timeout=10,
    )
    response.raise_for_status()
    token = response.json()["token"]
    expires_at = time.monotonic() + _COPILOT_TOKEN_TTL
    return token, expires_at


def _build_model() -> tuple[Model, float]:
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from angie.config import get_settings

    settings = get_settings()

    if settings.github_token:
        logger.info("LLM: using GitHub Copilot endpoint (%s)", settings.copilot_api_base)
        copilot_token, expires_at = _exchange_copilot_token(settings.github_token)
        provider = OpenAIProvider(
            base_url=settings.copilot_api_base,
            api_key=copilot_token,
        )
        return OpenAIModel(settings.copilot_model, provider=provider), expires_at

    if settings.openai_api_key:
        logger.info("LLM: using OpenAI (model=%s)", settings.copilot_model)
        provider = OpenAIProvider(api_key=settings.openai_api_key)
        return OpenAIModel(settings.copilot_model, provider=provider), float("inf")

    raise RuntimeError(
        "No LLM configured. Set GITHUB_TOKEN (GitHub Copilot) "
        "or OPENAI_API_KEY (OpenAI) in your .env file."
    )


def is_llm_configured() -> bool:
    """Return True if at least one LLM provider is configured."""
    from angie.config import get_settings

    s = get_settings()
    return bool(s.github_token or s.openai_api_key)
