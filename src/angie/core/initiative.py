"""Initiative engine — proactive scan loop that surfaces opportunities to users.

Examples of what scanners detect:
- New GitHub issues assigned to user
- Failed tasks that haven't been retried
- Stale PRs with no activity
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """A proactive suggestion surfaced to a user."""

    user_id: str
    message: str
    preferred_channel: str | None = None
    agent_slug: str | None = None
    auto_dispatchable: bool = False


class Scanner(ABC):
    """Base class for initiative scanners."""

    name: str = "base"

    @abstractmethod
    async def scan(self) -> list[Suggestion]:
        """Scan for proactive opportunities. Returns suggestions."""
        ...


class StaleTaskScanner(Scanner):
    """Finds failed tasks older than 1 hour that haven't been retried."""

    name = "stale_tasks"

    async def scan(self) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        try:
            from datetime import UTC, datetime, timedelta

            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.task import Task, TaskStatus

            cutoff = datetime.now(UTC) - timedelta(hours=1)
            async with get_session_factory()() as session:
                result = await session.execute(
                    select(Task).where(
                        Task.status == TaskStatus.FAILURE,
                        Task.created_at < cutoff,
                    )
                )
                tasks = result.scalars().all()
                for task in tasks[:5]:  # Limit suggestions
                    suggestions.append(
                        Suggestion(
                            user_id=task.user_id or "system",
                            message=f"Task '{task.title}' failed over an hour ago. "
                            f"Error: {task.error or 'unknown'}. Would you like to retry?",
                            agent_slug="task-manager",
                        )
                    )
        except Exception:
            logger.debug("StaleTaskScanner failed", exc_info=True)
        return suggestions


class GitHubIssueScanner(Scanner):
    """Checks for new issues assigned to the user."""

    name = "github_issues"

    async def scan(self) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        try:
            import os

            import github as gh_module

            token = os.environ.get("GITHUB_TOKEN", "")
            if not token:
                return suggestions

            g = gh_module.Github(token)
            user = g.get_user()
            issues = user.get_issues(state="open", filter="assigned")
            for issue in list(issues[:5]):
                # TODO: user_id should be resolved from a DB-backed
                # token→user mapping so suggestions reach the correct user
                # instead of the generic "system" identity.
                suggestions.append(
                    Suggestion(
                        user_id="system",
                        message=f"You have an assigned issue: [{issue.title}]({issue.html_url})",
                        agent_slug="github",
                    )
                )
        except Exception:
            logger.debug("GitHubIssueScanner failed", exc_info=True)
        return suggestions


class InitiativeEngine:
    """Periodically scans for proactive opportunities and surfaces them to users."""

    def __init__(self, scan_interval: int = 300) -> None:
        self._scanners: list[Scanner] = []
        self._scan_interval = scan_interval
        self._running = False

    def register_scanner(self, scanner: Scanner) -> None:
        """Register a scanner to run periodically."""
        self._scanners.append(scanner)
        logger.info("Registered initiative scanner: %s", scanner.name)

    async def start(self) -> None:
        """Start the periodic scan loop."""
        self._running = True
        # Register built-in scanners
        if not self._scanners:
            self._scanners = [
                StaleTaskScanner(),
                GitHubIssueScanner(),
            ]
        logger.info("Initiative engine started with %d scanners", len(self._scanners))
        while self._running:
            await self._run_scans()
            await asyncio.sleep(self._scan_interval)

    async def stop(self) -> None:
        """Stop the scan loop."""
        self._running = False

    async def _run_scans(self) -> None:
        """Execute all registered scanners."""
        for scanner in self._scanners:
            try:
                suggestions = await scanner.scan()
                for suggestion in suggestions:
                    await self._surface_suggestion(suggestion)
            except Exception:
                logger.exception("Scanner %s failed", scanner.name)

    async def _surface_suggestion(self, suggestion: Suggestion) -> None:
        """Notify the user about a proactive suggestion."""
        from angie.core.feedback import get_feedback

        feedback = get_feedback()
        await feedback.send_mention(
            suggestion.user_id,
            suggestion.message,
            channel=suggestion.preferred_channel,
        )
