"""GitHub repository and PR management agent."""

from __future__ import annotations

import os
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


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

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list_repos")
        self.logger.info("GitHubAgent action=%s", action)
        try:
            import github as gh_module

            token = os.environ.get("GITHUB_TOKEN", "")
            g = gh_module.Github(token) if token else gh_module.Github()
            return await self._dispatch(g, action, task.get("input_data", {}))
        except ImportError:
            return {"error": "PyGithub not installed"}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GitHubAgent error")
            return {"error": str(exc)}

    async def _dispatch(self, g: Any, action: str, data: dict[str, Any]) -> dict[str, Any]:
        repo_name: str = data.get("repo", "")

        if action == "list_repos":
            repos = [{"name": r.full_name, "private": r.private} for r in g.get_user().get_repos()[:20]]
            return {"repos": repos}

        if action == "list_prs":
            repo = g.get_repo(repo_name)
            prs = [
                {"number": pr.number, "title": pr.title, "state": pr.state, "author": pr.user.login}
                for pr in repo.get_pulls(state="open")[:20]
            ]
            return {"pull_requests": prs}

        if action == "list_issues":
            repo = g.get_repo(repo_name)
            issues = [
                {"number": i.number, "title": i.title, "state": i.state, "author": i.user.login}
                for i in repo.get_issues(state="open")[:20]
            ]
            return {"issues": issues}

        if action == "create_issue":
            repo = g.get_repo(repo_name)
            issue = repo.create_issue(
                title=data.get("title", "Untitled"),
                body=data.get("body", ""),
            )
            return {"created": True, "number": issue.number, "url": issue.html_url}

        if action == "get_repo":
            repo = g.get_repo(repo_name)
            return {
                "name": repo.full_name,
                "description": repo.description,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "default_branch": repo.default_branch,
            }

        return {"error": f"Unknown action: {action}"}

