"""Tests for remaining agent coverage gaps."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _task(action: str, **kw):
    return {"title": "t", "input_data": {"action": action, **kw}}


# ── GitHub ImportError ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_import_error():
    sys.modules.pop("angie.agents.dev.github", None)
    with patch.dict("sys.modules", {"github": None}):  # type: ignore[dict-item]
        import angie.agents.dev.github as _gh_mod

        agent = _gh_mod.GitHubAgent()
        result = await agent.execute(_task("list_repos"))
    sys.modules.pop("angie.agents.dev.github", None)
    # Restore: ensure next tests can freshly import the module
    import angie.agents.dev

    if hasattr(angie.agents.dev, "github"):
        delattr(angie.agents.dev, "github")

    assert result.get("error") == "PyGithub not installed"


# ── Registry module load exception ────────────────────────────────────────────


def test_registry_load_exception():
    """When a module raises ImportError during load_all, it's logged and skipped."""
    from angie.agents.registry import AgentRegistry

    registry = AgentRegistry()
    # Inject a bad module path into AGENT_MODULES temporarily
    with patch("angie.agents.registry.AGENT_MODULES", ["nonexistent.module.path"]):
        registry.load_all()
    # Should not raise; bad module is skipped
    assert registry._loaded is True


# ── Registry generic exception (lines 62-63) ──────────────────────────────────


def test_registry_generic_exception():
    """When a module raises a non-ImportError, it's logged and skipped."""
    from angie.agents.registry import AgentRegistry

    registry = AgentRegistry()

    # Use a module path that will raise a generic Exception during import
    with patch("angie.agents.registry.AGENT_MODULES", ["angie.agents.base"]):
        # Patch importlib.import_module to raise generic Exception
        with patch("importlib.import_module", side_effect=RuntimeError("boom")):
            registry.load_all()

    assert registry._loaded is True
