"""Prompt hierarchy manager.

Hierarchy:
    SYSTEM_PROMPT > ANGIE_PROMPT > AGENT_PROMPT    (for agent tasks)
    SYSTEM_PROMPT > ANGIE_PROMPT > USER_PROMPTS    (for user interactions)
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from angie.config import get_settings


class PromptManager:
    """Loads, renders, and composes the prompt hierarchy."""

    def __init__(self, prompts_dir: str | None = None) -> None:
        settings = get_settings()
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self.user_prompts_dir = Path(settings.user_prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader([str(self.prompts_dir), str(self.user_prompts_dir)]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._cache: dict[str, str] = {}

    def _render(self, template_name: str, context: dict | None = None) -> str:
        key = f"{template_name}:{context}"
        if key not in self._cache:
            template = self._env.get_template(template_name)
            self._cache[key] = template.render(**(context or {}))
        return self._cache[key]

    def _load_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def get_system_prompt(self, context: dict | None = None) -> str:
        try:
            return self._render("system.md", context)
        except Exception:
            return self._load_file(self.prompts_dir / "system.md")

    def get_angie_prompt(self, context: dict | None = None) -> str:
        try:
            return self._render("angie.md", context)
        except Exception:
            return self._load_file(self.prompts_dir / "angie.md")

    def get_agent_prompt(self, agent_slug: str, context: dict | None = None) -> str:
        template_name = f"agents/{agent_slug}.md"
        try:
            return self._render(template_name, context)
        except Exception:
            path = self.prompts_dir / "agents" / f"{agent_slug}.md"
            return self._load_file(path)

    def get_user_prompts(self, user_id: str, context: dict | None = None) -> list[str]:
        user_dir = self.user_prompts_dir / user_id
        if not user_dir.exists():
            return []
        prompts = []
        for md_file in sorted(user_dir.glob("*.md")):
            prompts.append(md_file.read_text(encoding="utf-8"))
        return prompts

    def compose_for_agent(
        self,
        agent_slug: str,
        context: dict | None = None,
        agent_instructions: str = "",
    ) -> str:
        """Compose: SYSTEM > ANGIE > AGENT_PROMPT/INSTRUCTIONS."""
        # Use inline instructions if provided, otherwise load from file
        agent_prompt = agent_instructions or self.get_agent_prompt(agent_slug, context)
        parts = [
            self.get_system_prompt(context),
            self.get_angie_prompt(context),
            agent_prompt,
        ]
        return "\n\n---\n\n".join(p for p in parts if p.strip())

    def compose_for_user(
        self,
        user_id: str,
        context: dict | None = None,
    ) -> str:
        """Compose: SYSTEM > ANGIE > USER_PROMPTS."""
        parts = [
            self.get_system_prompt(context),
            self.get_angie_prompt(context),
            *self.get_user_prompts(user_id, context),
        ]
        return "\n\n---\n\n".join(p for p in parts if p.strip())

    def invalidate_cache(self) -> None:
        self._cache.clear()

    def save_user_prompt(self, user_id: str, name: str, content: str) -> Path:
        """Persist a USER_PROMPT markdown file."""
        user_dir = self.user_prompts_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return path


_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager
