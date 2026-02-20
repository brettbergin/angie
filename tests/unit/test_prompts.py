"""Unit tests for the prompt manager."""

import pytest

from angie.core.prompts import PromptManager


@pytest.fixture
def tmp_prompt_manager(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    user_dir = tmp_path / "prompts" / "user"
    user_dir.mkdir()

    (prompts_dir / "system.md").write_text("# System\nYou are Angie.")
    (prompts_dir / "angie.md").write_text("# Angie\nBe helpful.")

    pm = PromptManager(prompts_dir=str(prompts_dir))
    pm.user_prompts_dir = user_dir
    return pm


def test_get_system_prompt(tmp_prompt_manager):
    prompt = tmp_prompt_manager.get_system_prompt()
    assert "Angie" in prompt


def test_get_angie_prompt(tmp_prompt_manager):
    prompt = tmp_prompt_manager.get_angie_prompt()
    assert "helpful" in prompt


def test_get_user_prompts_empty(tmp_prompt_manager):
    prompts = tmp_prompt_manager.get_user_prompts("new-user")
    assert prompts == []


def test_save_and_get_user_prompt(tmp_prompt_manager):
    tmp_prompt_manager.save_user_prompt("user-1", "personality", "# Personality\nI like brevity.")
    prompts = tmp_prompt_manager.get_user_prompts("user-1")
    assert len(prompts) == 1
    assert "brevity" in prompts[0]


def test_compose_for_user(tmp_prompt_manager):
    tmp_prompt_manager.save_user_prompt("user-1", "prefs", "# Prefs\nKeep it short.")
    composed = tmp_prompt_manager.compose_for_user("user-1")
    assert "Angie" in composed
    assert "short" in composed


def test_invalidate_cache(tmp_prompt_manager):
    tmp_prompt_manager.get_system_prompt()
    assert len(tmp_prompt_manager._cache) > 0
    tmp_prompt_manager.invalidate_cache()
    assert len(tmp_prompt_manager._cache) == 0
