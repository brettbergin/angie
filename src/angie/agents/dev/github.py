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
    category: ClassVar[str] = "Social Agents"
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
        "- list_pull_requests: List PRs for a repo. Specify repo as 'owner/name'.\n"
        "- list_issues: List issues for a repo. Same repo format and state filter.\n"
        "- create_issue: Create a new issue. Requires repo, title, and optional body.\n"
        "- get_repository: Get repo details including stars, forks, and default branch.\n"
        "- comment_on_issue: Add a comment to an existing issue.\n"
        "- comment_on_pr: Add a review comment to a pull request.\n"
        "- merge_pull_request: Merge a PR (supports merge, squash, or rebase).\n"
        "- close_issue: Close an open issue.\n"
        "- list_pr_checks: Get CI check status for a PR.\n"
        "- get_pr_diff: Get the diff/changed files for a PR.\n"
        "- search_issues: Search issues and PRs with a query string.\n\n"
        "Requires GITHUB_TOKEN environment variable. Repo names must be in 'owner/repo' format.\n\n"
        "Error handling:\n"
        "- If you get a rate limit error (403), inform the user they've hit the GitHub API "
        "rate limit and suggest waiting a few minutes.\n"
        "- If you get an auth error (401), tell the user to check their GitHub token.\n"
        "- If a repo is not found (404), verify the repo name format is 'owner/repo'.\n"
        "- If list_pull_requests returns empty, inform the user there are no PRs "
        "matching the criteria rather than calling other tools.\n\n"
        "IMPORTANT — formatting rules for your response:\n"
        "- Always render PR and issue references as Markdown hyperlinks using the url field "
        "from tool results, e.g. [#42](https://github.com/owner/repo/pull/42).\n"
        "- Repository names should link to the repo, e.g. "
        "[owner/repo](https://github.com/owner/repo).\n"
        "- Never output bare numbers like #42 without a hyperlink.\n"
        "- Format CI check results clearly with status icons."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def list_repositories(ctx: RunContext[object]) -> list | dict:
            """List the authenticated user's GitHub repositories."""
            try:
                g = ctx.deps
                return [
                    {"name": r.full_name, "private": r.private}
                    for r in list(g.get_user().get_repos()[:20])
                ]
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def list_pull_requests(
            ctx: RunContext[object], repo: str, state: str = "open"
        ) -> list | dict:
            """List pull requests for a GitHub repository."""
            try:
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
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def list_issues(ctx: RunContext[object], repo: str, state: str = "open") -> list | dict:
            """List issues for a GitHub repository."""
            try:
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
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def create_issue(ctx: RunContext[object], repo: str, title: str, body: str = "") -> dict:
            """Create a new issue in a GitHub repository."""
            try:
                g = ctx.deps
                issue = g.get_repo(repo).create_issue(title=title, body=body)
                return {"created": True, "number": issue.number, "url": issue.html_url}
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def get_repository(ctx: RunContext[object], repo: str) -> dict:
            """Get details about a GitHub repository."""
            try:
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
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def comment_on_issue(ctx: RunContext[object], repo: str, number: int, body: str) -> dict:
            """Add a comment to an existing issue."""
            try:
                g = ctx.deps
                issue = g.get_repo(repo).get_issue(number)
                comment = issue.create_comment(body)
                return {"commented": True, "comment_id": comment.id, "issue_number": number}
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def comment_on_pr(ctx: RunContext[object], repo: str, number: int, body: str) -> dict:
            """Add a review comment to a pull request."""
            try:
                g = ctx.deps
                pr = g.get_repo(repo).get_pull(number)
                # Create an issue comment on the PR (general comment, not line-level)
                comment = pr.create_issue_comment(body)
                return {"commented": True, "comment_id": comment.id, "pr_number": number}
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def merge_pull_request(
            ctx: RunContext[object], repo: str, number: int, merge_method: str = "merge"
        ) -> dict:
            """Merge a pull request. merge_method: 'merge', 'squash', or 'rebase'."""
            try:
                g = ctx.deps
                pr = g.get_repo(repo).get_pull(number)
                if pr.merged:
                    return {"error": f"PR #{number} is already merged."}
                if not pr.mergeable:
                    return {
                        "error": f"PR #{number} has merge conflicts that must be resolved first."
                    }
                result = pr.merge(merge_method=merge_method)
                return {
                    "merged": result.merged,
                    "message": result.message,
                    "sha": result.sha,
                    "pr_number": number,
                }
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def close_issue(ctx: RunContext[object], repo: str, number: int) -> dict:
            """Close an open issue."""
            try:
                g = ctx.deps
                issue = g.get_repo(repo).get_issue(number)
                issue.edit(state="closed")
                return {"closed": True, "number": number, "url": issue.html_url}
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def list_pr_checks(ctx: RunContext[object], repo: str, number: int) -> dict:
            """Get CI check status for a pull request."""
            try:
                g = ctx.deps
                repository = g.get_repo(repo)
                pr = repository.get_pull(number)
                commit = repository.get_commit(pr.head.sha)
                checks = []
                for run in commit.get_check_runs():
                    checks.append(
                        {
                            "name": run.name,
                            "status": run.status,
                            "conclusion": run.conclusion,
                            "url": run.html_url,
                        }
                    )
                combined_status = commit.get_combined_status()
                return {
                    "pr_number": number,
                    "overall_state": combined_status.state,
                    "checks": checks,
                }
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def get_pr_diff(ctx: RunContext[object], repo: str, number: int) -> dict:
            """Get the changed files and diff stats for a pull request."""
            try:
                g = ctx.deps
                pr = g.get_repo(repo).get_pull(number)
                files = []
                for f in pr.get_files():
                    files.append(
                        {
                            "filename": f.filename,
                            "status": f.status,
                            "additions": f.additions,
                            "deletions": f.deletions,
                            "changes": f.changes,
                            "patch": (f.patch or "")[:2000],  # Truncate large patches
                        }
                    )
                return {
                    "pr_number": number,
                    "files_changed": len(files),
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "files": files,
                }
            except Exception as exc:
                return _handle_github_error(exc)

        @agent.tool
        def search_issues(ctx: RunContext[object], repo: str, query: str) -> list | dict:
            """Search issues and PRs in a repo with a query string."""
            try:
                g = ctx.deps
                full_query = f"repo:{repo} {query}"
                results = []
                for issue in g.search_issues(full_query):
                    results.append(
                        {
                            "number": issue.number,
                            "title": issue.title,
                            "state": issue.state,
                            "is_pr": issue.pull_request is not None,
                            "author": issue.user.login,
                            "url": issue.html_url,
                        }
                    )
                    if len(results) >= 20:
                        break
                return results
            except Exception as exc:
                return _handle_github_error(exc)

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
            token = (
                (creds or {}).get("personal_access_token")
                or (creds or {}).get("token")
                or os.environ.get("GITHUB_TOKEN", "")
            )
            g = gh_module.Github(token) if token else gh_module.Github()
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="list my repositories")
            conversation_id = task.get("input_data", {}).get("conversation_id")
            if conversation_id:
                history = await self.get_conversation_history(conversation_id)
                prompt = self._build_context_prompt(intent, history)
            else:
                prompt = intent
            result = await self._get_agent().run(prompt, model=get_llm_model(), deps=g)
            return {"summary": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GitHubAgent error")
            return {"summary": f"GitHub error: {exc}", "error": str(exc)}


def _handle_github_error(exc: Exception) -> dict:
    """Return an actionable error dict for common GitHub API failures."""
    import github as gh_module

    if isinstance(exc, gh_module.RateLimitExceededException):
        return {
            "error": "GitHub API rate limit exceeded. Please wait a few minutes and try again.",
            "retry_after_seconds": 60,
        }
    if isinstance(exc, gh_module.BadCredentialsException):
        return {
            "error": (
                "GitHub authentication failed. Please verify your Personal Access Token "
                "has the required scopes (repo, read:org) and has not expired."
            ),
        }
    if isinstance(exc, gh_module.UnknownObjectException):
        return {
            "error": (
                f"Resource not found: {exc}. Verify the repo name is in 'owner/repo' format "
                "and that you have access to it."
            ),
        }
    if isinstance(exc, gh_module.GithubException):
        return {"error": f"GitHub API error ({exc.status}): {exc.data.get('message', str(exc))}"}
    return {"error": f"Unexpected error: {exc}"}
