"""Software Developer agent — autonomous issue-to-PR workflow."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


_BLOCKED_COMMANDS = re.compile(
    r"rm\s+-rf\s+/|mkfs|dd\s+if=|shutdown|reboot|halt|poweroff|:(){ :|fork\s*bomb",
    re.IGNORECASE,
)
_COMMAND_TIMEOUT = 120


@dataclass
class SoftwareDevDeps:
    """Dependencies injected into pydantic-ai tool context."""

    github_token: str = ""
    workspace_dir: Path = field(default_factory=lambda: Path(tempfile.mkdtemp()))
    user_id: str = ""
    repo_dir: Path | None = None


class SoftwareDeveloperAgent(BaseAgent):
    name: ClassVar[str] = "SoftwareDeveloper"
    slug: ClassVar[str] = "software-dev"
    category: ClassVar[str] = "Developer Agents"
    description: ClassVar[str] = (
        "Autonomous software developer that turns GitHub issues into pull requests."
    )
    capabilities: ClassVar[list[str]] = [
        "software development",
        "coding",
        "pull request",
        "issue",
        "branch",
        "commit",
        "code review",
    ]
    instructions: ClassVar[str] = (
        "You are an autonomous software developer. Given a GitHub issue URL, you:\n"
        "1. Fetch the issue to understand requirements\n"
        "2. Clone the repository\n"
        "3. Create a feature branch\n"
        "4. Explore the codebase to understand context\n"
        "5. Implement the required changes\n"
        "6. Run tests/linting to validate\n"
        "7. Commit and push your changes\n"
        "8. Open a pull request referencing the issue\n\n"
        "Follow these conventions:\n"
        "- Branch naming: angie/issue-{number}-{short-slug}\n"
        "- Commit messages: conventional commits format, e.g. feat(scope): description (#N)\n"
        "- PR body must include 'Closes #N' to auto-link the issue\n"
        "- Make minimal, focused changes\n"
        "- Always run tests if a test suite exists\n"
        "- Return the PR URL as a clickable HTML link in your final response"
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[SoftwareDevDeps, str] = Agent(
            deps_type=SoftwareDevDeps,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def fetch_issue(ctx: RunContext[SoftwareDevDeps], issue_url: str) -> dict:
            """Fetch a GitHub issue by URL. Returns title, body, labels, and comments."""
            import github as gh_module

            owner, repo, number = _parse_issue_url(issue_url)
            g = (
                gh_module.Github(ctx.deps.github_token)
                if ctx.deps.github_token
                else gh_module.Github()
            )
            repo_obj = g.get_repo(f"{owner}/{repo}")
            issue = repo_obj.get_issue(number)
            comments = [{"author": c.user.login, "body": c.body} for c in issue.get_comments()[:10]]
            return {
                "owner": owner,
                "repo": repo,
                "number": number,
                "title": issue.title,
                "body": issue.body or "",
                "labels": [lb.name for lb in issue.labels],
                "comments": comments,
                "default_branch": repo_obj.default_branch,
            }

        @agent.tool
        def clone_repo(ctx: RunContext[SoftwareDevDeps], repo: str, branch: str = "") -> dict:
            """Clone a GitHub repository into the workspace. ``repo`` is 'owner/name'."""
            repo_dir = ctx.deps.workspace_dir / repo.replace("/", "_")
            if repo_dir.exists():
                _run_git(["git", "pull"], cwd=repo_dir)
            else:
                clone_url = f"https://x-access-token:{ctx.deps.github_token}@github.com/{repo}.git"
                _run_git(["git", "clone", clone_url, str(repo_dir)])
            if branch:
                _run_git(["git", "checkout", branch], cwd=repo_dir)
            ctx.deps.repo_dir = repo_dir
            return {"cloned": True, "repo_dir": str(repo_dir), "branch": branch or "default"}

        @agent.tool
        def create_branch(ctx: RunContext[SoftwareDevDeps], branch_name: str) -> dict:
            """Create and checkout a new branch in the cloned repo."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet. Call clone_repo first."}
            _run_git(["git", "checkout", "-b", branch_name], cwd=ctx.deps.repo_dir)
            return {"created": True, "branch": branch_name}

        @agent.tool
        def read_file(ctx: RunContext[SoftwareDevDeps], path: str) -> dict:
            """Read a file from the cloned repository."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            file_path = ctx.deps.repo_dir / path
            if not file_path.is_file():
                return {"error": f"File not found: {path}"}
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if len(content) > 50_000:
                    content = content[:50_000] + "\n... (truncated)"
                return {"path": path, "content": content}
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool
        def list_directory(ctx: RunContext[SoftwareDevDeps], path: str = ".") -> dict:
            """List contents of a directory in the cloned repository."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            dir_path = ctx.deps.repo_dir / path
            if not dir_path.is_dir():
                return {"error": f"Directory not found: {path}"}
            entries = []
            for entry in sorted(dir_path.iterdir()):
                if entry.name.startswith("."):
                    continue
                entries.append(
                    {
                        "name": entry.name,
                        "type": "dir" if entry.is_dir() else "file",
                    }
                )
            return {"path": path, "entries": entries}

        @agent.tool
        def search_code(ctx: RunContext[SoftwareDevDeps], pattern: str) -> dict:
            """Search the codebase for a pattern using grep."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            try:
                result = subprocess.run(
                    [
                        "grep",
                        "-rn",
                        "--include=*.py",
                        "--include=*.ts",
                        "--include=*.tsx",
                        "--include=*.js",
                        "--include=*.jsx",
                        "--include=*.md",
                        pattern,
                    ],
                    cwd=ctx.deps.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                lines = result.stdout.strip().split("\n")[:50]
                return {"pattern": pattern, "matches": [line for line in lines if line]}
            except subprocess.TimeoutExpired:
                return {"error": "Search timed out"}

        @agent.tool
        def write_file(ctx: RunContext[SoftwareDevDeps], path: str, content: str) -> dict:
            """Write or overwrite a file in the cloned repository."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            file_path = ctx.deps.repo_dir / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {"written": True, "path": path, "size": len(content)}

        @agent.tool
        def run_command(ctx: RunContext[SoftwareDevDeps], command: str) -> dict:
            """Run a shell command in the repository directory. Has a timeout and blocks dangerous commands."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            if _BLOCKED_COMMANDS.search(command):
                return {"error": "Command blocked for safety reasons."}
            try:
                result = subprocess.run(
                    shlex.split(command),
                    cwd=ctx.deps.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=_COMMAND_TIMEOUT,
                )
                output = result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout
                stderr = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                return {
                    "returncode": result.returncode,
                    "stdout": output,
                    "stderr": stderr,
                }
            except subprocess.TimeoutExpired:
                return {"error": f"Command timed out after {_COMMAND_TIMEOUT}s"}

        @agent.tool
        def commit_and_push(ctx: RunContext[SoftwareDevDeps], message: str) -> dict:
            """Stage all changes, commit with the given message, and push."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            cwd = ctx.deps.repo_dir
            _run_git(["git", "add", "-A"], cwd=cwd)
            _run_git(["git", "commit", "-m", message], cwd=cwd)
            result = _run_git(["git", "push", "-u", "origin", "HEAD"], cwd=cwd)
            # Extract the current branch
            branch_result = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
            sha_result = _run_git(["git", "rev-parse", "HEAD"], cwd=cwd)
            return {
                "committed": True,
                "branch": branch_result.stdout.strip(),
                "sha": sha_result.stdout.strip(),
                "push_output": result.stdout.strip() + result.stderr.strip(),
            }

        @agent.tool
        def create_pull_request(
            ctx: RunContext[SoftwareDevDeps],
            repo: str,
            branch: str,
            title: str,
            body: str,
            issue_number: int = 0,
        ) -> dict:
            """Open a pull request via the GitHub API."""
            import github as gh_module

            g = (
                gh_module.Github(ctx.deps.github_token)
                if ctx.deps.github_token
                else gh_module.Github()
            )
            repo_obj = g.get_repo(repo)

            if issue_number and f"#{issue_number}" not in body:
                body += f"\n\nCloses #{issue_number}"

            pr = repo_obj.create_pull(
                title=title,
                body=body,
                head=branch,
                base=repo_obj.default_branch,
            )
            return {
                "created": True,
                "pr_number": pr.number,
                "pr_url": pr.html_url,
                "title": pr.title,
            }

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        try:
            import github as gh_module  # noqa: F401
        except ImportError:
            return {"error": "PyGithub not installed"}

        self.logger.info("SoftwareDeveloperAgent executing")
        workspace_dir = Path(tempfile.mkdtemp(prefix="angie-workspace-"))

        try:
            user_id = task.get("user_id")
            creds = await self.get_credentials(user_id, "github")
            token = (
                (creds or {}).get("personal_access_token")
                or (creds or {}).get("token")
                or os.environ.get("GITHUB_TOKEN", "")
            )

            deps = SoftwareDevDeps(
                github_token=token,
                workspace_dir=workspace_dir,
                user_id=user_id or "",
            )

            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="")
            if not intent:
                return {"error": "No issue URL or instructions provided."}

            result = await self._get_agent().run(intent, model=get_llm_model(), deps=deps)
            return {"summary": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("SoftwareDeveloperAgent error")
            return {"summary": f"Software dev error: {exc}", "error": str(exc)}
        finally:
            # Clean up workspace
            if workspace_dir.exists():
                shutil.rmtree(workspace_dir, ignore_errors=True)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_issue_url(url: str) -> tuple[str, str, int]:
    """Extract (owner, repo, issue_number) from a GitHub issue URL."""
    # https://github.com/owner/repo/issues/42
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if match:
        return match.group(1), match.group(2), int(match.group(3))
    # Fallback: try #N format with repo context
    match = re.search(r"([^/\s]+)/([^/\s]+)#(\d+)", url)
    if match:
        return match.group(1), match.group(2), int(match.group(3))
    raise ValueError(f"Could not parse GitHub issue URL: {url!r}")


def _run_git(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
