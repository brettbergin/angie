"""GitHub repository and PR management agent."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class GitHubAgent(BaseAgent):
    name: ClassVar[str] = "GitHubAgent"
    slug: ClassVar[str] = "github"
    description: ClassVar[str] = "GitHub repository and PR management."
    capabilities: ClassVar[list[str]] = [
        "github",
        "pull request",
        "pr",
        "issues",
        "repository",
        "commit",
    ]
    instructions: ClassVar[str] = (
        "You manage GitHub repositories, pull requests, and issues via the GitHub API.\n\n"
        "Available tools:\n"
        "- list_repositories: List the authenticated user's repos (up to 20).\n"
        "- list_pull_requests: List PRs for a repo. Specify repo as 'owner/name' and "
        "optionally filter by state (open, closed, all).\n"
        "- list_issues: List issues for a repo. Same repo format and state filter.\n"
        "- create_issue: Create a new issue. Requires repo, title, and optional body.\n"
        "- get_repository: Get repo details including stars, forks, and default branch.\n\n"
        "Requires GITHUB_TOKEN environment variable. Repo names must be in 'owner/repo' format.\n\n"
        "IMPORTANT — formatting rules for your response:\n"
        "- Always render PR and issue references as Markdown hyperlinks using the url field "
        "from tool results, e.g. [#42](https://github.com/owner/repo/pull/42).\n"
        "- Repository names should link to the repo, e.g. "
        "[owner/repo](https://github.com/owner/repo).\n"
        "- Never output bare numbers like #42 without a hyperlink."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def list_repositories(ctx: RunContext[object]) -> list:
            """List the authenticated user's GitHub repositories."""
            g = ctx.deps
            return [
                {"name": r.full_name, "private": r.private}
                for r in list(g.get_user().get_repos()[:20])
            ]

        @agent.tool
        def list_pull_requests(ctx: RunContext[object], repo: str, state: str = "open") -> list:
            """List pull requests for a GitHub repository."""
            g = ctx.deps
            repo_obj = g.get_repo(repo)
            pulls = []
            for pr in repo_obj.get_pulls(state=state):
                pulls.append(
                    {
                        "number": pr.number,
                        "title": pr.title,
                        "state": pr.state,
                        "author": pr.user.login,
                        "url": pr.html_url,
                    }
                )
                if len(pulls) >= 20:
                    break
            return pulls

        @agent.tool
        def list_issues(ctx: RunContext[object], repo: str, state: str = "open") -> list:
            """List issues for a GitHub repository."""
            g = ctx.deps
            repo_obj = g.get_repo(repo)
            issues = []
            for i in repo_obj.get_issues(state=state):
                issues.append(
                    {
                        "number": i.number,
                        "title": i.title,
                        "state": i.state,
                        "author": i.user.login,
                        "url": i.html_url,
                    }
                )
                if len(issues) >= 20:
                    break
            return issues

        @agent.tool
        def create_issue(ctx: RunContext[object], repo: str, title: str, body: str = "") -> dict:
            """Create a new issue in a GitHub repository."""
            g = ctx.deps
            issue = g.get_repo(repo).create_issue(title=title, body=body)
            return {"created": True, "number": issue.number, "url": issue.html_url}

        @agent.tool
        def get_repository(ctx: RunContext[object], repo: str) -> dict:
            """Get details about a GitHub repository."""
            g = ctx.deps
            r = g.get_repo(repo)
            return {
                "name": r.full_name,
                "description": r.description,
                "stars": r.stargazers_count,
                "forks": r.forks_count,
                "open_issues": r.open_issues_count,
                "default_branch": r.default_branch,
                "url": r.html_url,
            }

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        try:
            import github as gh_module
        except ImportError:
            return {"error": "PyGithub not installed"}
        self.logger.info("GitHubAgent executing")
        try:
            user_id = task.get("user_id")
            creds = await self.get_credentials(user_id, "github")
            token = (creds or {}).get("token") or os.environ.get("GITHUB_TOKEN", "")
            g = gh_module.Github(token) if token else gh_module.Github()
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="list my repositories")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=g)
            return {"summary": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GitHubAgent error")
            return {"summary": f"GitHub error: {exc}", "error": str(exc)}
