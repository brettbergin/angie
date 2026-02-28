"""Software Developer agent — autonomous issue-to-PR workflow."""

from __future__ import annotations

import os
import re
import shutil
import stat
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
_SHELL_INJECTION = re.compile(
    r"[;`]|\$\(|&&\s*(?:rm|curl|wget|nc|bash|sh\b)|"
    r"\|\s*(?:rm|curl|wget|nc|bash|sh\b)|>\s*/(?:etc|dev|proc)",
)
_COMMAND_TIMEOUT = 120
_MAX_FILE_SIZE = 100 * 1024  # 100KB
_MAX_WORKSPACE_SIZE = 500 * 1024 * 1024  # 500MB
_BRANCH_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._/-]+$")


@dataclass
class SoftwareDevDeps:
    """Dependencies injected into pydantic-ai tool context."""

    github_token: str = ""
    workspace_dir: Path = field(default_factory=lambda: Path(tempfile.mkdtemp()))
    user_id: str = ""
    repo_dir: Path | None = None
    _git_env: dict[str, str] = field(default_factory=dict, repr=False)


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
        "You are an autonomous software developer. The user message will contain a GitHub "
        "issue URL (e.g. https://github.com/owner/repo/issues/42). "
        "Immediately call `fetch_issue` with that URL — do NOT ask the user for it.\n\n"
        "After fetching the issue, follow this workflow:\n"
        "1. Clone the repository\n"
        "2. Create a feature branch\n"
        "3. Explore the codebase to understand context\n"
        "4. Implement the required changes\n"
        "5. Run tests/linting to validate\n"
        "6. Commit and push your changes\n"
        "7. Open a pull request referencing the issue\n\n"
        "Follow these conventions:\n"
        "- Branch naming: angie/issue-{number}-{short-slug}\n"
        "- Commit messages: conventional commits format, e.g. feat(scope): description (#N)\n"
        "- PR body must include 'Closes #N' to auto-link the issue\n"
        "- Make minimal, focused changes\n"
        "- Always run tests if a test suite exists\n"
        "- Return the PR URL as a clickable HTML link in your final response\n\n"
        "Fallback strategies:\n"
        "- If `run_command` for tests fails, use `run_tests` to read test output and explain "
        "what went wrong.\n"
        "- If `clone_repo` fails with auth error, inform the user their GitHub token needs "
        "'repo' scope.\n"
        "- If `create_pull_request` fails because the branch already exists, try updating the "
        "existing PR instead.\n"
        "- If the issue is too complex, break it into sub-tasks and explain what you can and "
        "cannot do.\n"
        "- Always use `check_ci_status` after opening a PR to verify CI passes."
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

            try:
                owner, repo, number = _parse_issue_url(issue_url)
                g = (
                    gh_module.Github(ctx.deps.github_token)
                    if ctx.deps.github_token
                    else gh_module.Github()
                )
                repo_obj = g.get_repo(f"{owner}/{repo}")
                issue = repo_obj.get_issue(number)
                comments = [
                    {"author": c.user.login, "body": c.body}
                    for _, c in zip(range(10), issue.get_comments(), strict=False)
                ]
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
            except ValueError as exc:
                return {"error": str(exc)}
            except Exception as exc:
                return {"error": f"Failed to fetch issue: {exc}"}

        @agent.tool
        def clone_repo(ctx: RunContext[SoftwareDevDeps], repo: str, branch: str = "") -> dict:
            """Clone a GitHub repository into the workspace. ``repo`` is 'owner/name'."""
            repo_dir = ctx.deps.workspace_dir / repo.replace("/", "_")
            git_env = _build_git_env(ctx.deps.github_token, ctx.deps.workspace_dir)
            ctx.deps._git_env = git_env
            try:
                if repo_dir.exists():
                    _run_git(["git", "pull"], cwd=repo_dir, env=git_env)
                else:
                    clone_url = f"https://github.com/{repo}.git"
                    _run_git(["git", "clone", clone_url, str(repo_dir)], env=git_env)
                # Configure git identity for commits
                _run_git(["git", "config", "user.email", "angie@angie.bot"], cwd=repo_dir, env=git_env)
                _run_git(["git", "config", "user.name", "Angie"], cwd=repo_dir, env=git_env)
                if branch:
                    _run_git(["git", "checkout", branch], cwd=repo_dir, env=git_env)
                ctx.deps.repo_dir = repo_dir
                return {"cloned": True, "repo_dir": str(repo_dir), "branch": branch or "default"}
            except subprocess.CalledProcessError as exc:
                err_msg = _sanitize_token(exc.stderr or exc.output or "", ctx.deps.github_token)
                return {"error": _classify_git_error(exc.returncode, err_msg)}

        @agent.tool
        def create_branch(ctx: RunContext[SoftwareDevDeps], branch_name: str) -> dict:
            """Create and checkout a new branch in the cloned repo."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet. Call clone_repo first."}
            if not _BRANCH_NAME_PATTERN.match(branch_name):
                return {
                    "error": (
                        f"Invalid branch name '{branch_name}'. "
                        "Use only alphanumeric characters, dots, hyphens, underscores, and slashes."
                    )
                }
            try:
                _run_git(
                    ["git", "checkout", "-b", branch_name], cwd=ctx.deps.repo_dir, env=ctx.deps._git_env
                )
                return {"created": True, "branch": branch_name}
            except subprocess.CalledProcessError as exc:
                err_msg = _sanitize_token(exc.stderr or "", ctx.deps.github_token)
                return {"error": f"Failed to create branch: {err_msg}"}

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
            if len(content.encode("utf-8")) > _MAX_FILE_SIZE:
                return {
                    "error": (
                        f"File content exceeds {_MAX_FILE_SIZE // 1024}KB limit. "
                        "Break the content into smaller files."
                    )
                }
            # Check workspace size
            workspace_size = _get_dir_size(ctx.deps.workspace_dir)
            if workspace_size > _MAX_WORKSPACE_SIZE:
                return {
                    "error": (
                        f"Workspace exceeds {_MAX_WORKSPACE_SIZE // (1024 * 1024)}MB limit. "
                        "Clean up unnecessary files first."
                    )
                }
            file_path = ctx.deps.repo_dir / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {"written": True, "path": path, "size": len(content)}

        @agent.tool
        def apply_patch(ctx: RunContext[SoftwareDevDeps], path: str, patch_content: str) -> dict:
            """Apply a unified diff patch to a file in the repository."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            try:
                result = subprocess.run(
                    ["patch", "-p0", "--no-backup-if-mismatch"],
                    input=patch_content,
                    cwd=ctx.deps.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return {"applied": True, "output": result.stdout.strip()}
                return {"error": f"Patch failed: {result.stderr.strip() or result.stdout.strip()}"}
            except subprocess.TimeoutExpired:
                return {"error": "Patch application timed out"}

        @agent.tool
        def run_tests(ctx: RunContext[SoftwareDevDeps], test_command: str = "") -> dict:
            """Run the test suite. Auto-detects pytest/npm test if no command given."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            repo_dir = ctx.deps.repo_dir

            # Auto-detect test command if not provided
            if not test_command:
                if (repo_dir / "pyproject.toml").exists() or (repo_dir / "setup.py").exists():
                    test_command = "python -m pytest -x --tb=short -q"
                elif (repo_dir / "package.json").exists():
                    test_command = "npm test"
                elif (repo_dir / "Makefile").exists():
                    test_command = "make test"
                else:
                    return {"error": "No test framework detected. Provide a test_command."}

            if _BLOCKED_COMMANDS.search(test_command) or _SHELL_INJECTION.search(test_command):
                return {"error": "Test command blocked for safety reasons."}

            try:
                result = subprocess.run(
                    ["sh", "-c", test_command],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutes for tests
                    env={**os.environ, **ctx.deps._git_env},
                )
                stdout = result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout
                stderr = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                return {
                    "passed": result.returncode == 0,
                    "returncode": result.returncode,
                    "stdout": _sanitize_token(stdout, ctx.deps.github_token),
                    "stderr": _sanitize_token(stderr, ctx.deps.github_token),
                }
            except subprocess.TimeoutExpired:
                return {"error": "Tests timed out after 5 minutes"}

        @agent.tool
        def check_ci_status(ctx: RunContext[SoftwareDevDeps], repo: str, branch: str) -> dict:
            """Check CI/check status for a branch after pushing."""
            try:
                import github as gh_module

                g = (
                    gh_module.Github(ctx.deps.github_token)
                    if ctx.deps.github_token
                    else gh_module.Github()
                )
                repo_obj = g.get_repo(repo)
                branch_obj = repo_obj.get_branch(branch)
                commit = repo_obj.get_commit(branch_obj.commit.sha)

                checks = []
                for run in commit.get_check_runs():
                    checks.append(
                        {
                            "name": run.name,
                            "status": run.status,
                            "conclusion": run.conclusion,
                        }
                    )

                combined = commit.get_combined_status()
                return {
                    "branch": branch,
                    "overall_state": combined.state,
                    "checks": checks,
                    "total_checks": len(checks),
                }
            except Exception as exc:
                return {"error": f"Failed to check CI status: {exc}"}

        @agent.tool
        def run_command(ctx: RunContext[SoftwareDevDeps], command: str) -> dict:
            """Run a shell command in the repository directory. Has a timeout and blocks dangerous commands."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            if _BLOCKED_COMMANDS.search(command) or _SHELL_INJECTION.search(command):
                return {"error": "Command blocked for safety reasons."}
            try:
                result = subprocess.run(
                    ["sh", "-c", command],
                    cwd=ctx.deps.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=_COMMAND_TIMEOUT,
                    env={**os.environ, **ctx.deps._git_env},
                )
                output = result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout
                stderr = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                return {
                    "returncode": result.returncode,
                    "stdout": _sanitize_token(output, ctx.deps.github_token),
                    "stderr": _sanitize_token(stderr, ctx.deps.github_token),
                }
            except subprocess.TimeoutExpired:
                return {"error": f"Command timed out after {_COMMAND_TIMEOUT}s"}

        @agent.tool
        def commit_and_push(ctx: RunContext[SoftwareDevDeps], message: str) -> dict:
            """Stage all changes, commit with the given message, and push with lease protection."""
            if not ctx.deps.repo_dir:
                return {"error": "No repository cloned yet."}
            cwd = ctx.deps.repo_dir
            git_env = ctx.deps._git_env
            try:
                _run_git(["git", "add", "-A"], cwd=cwd, env=git_env)
                _run_git(["git", "commit", "-m", message], cwd=cwd, env=git_env)
                # Use --force-with-lease for safe push that rejects if remote has diverged
                _run_git(["git", "push", "--force-with-lease", "-u", "origin", "HEAD"], cwd=cwd, env=git_env)
            except subprocess.CalledProcessError as exc:
                err_msg = _sanitize_token(exc.stderr or exc.output or "", ctx.deps.github_token)
                return {"error": _classify_git_error(exc.returncode, err_msg)}
            branch_result = _run_git(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, env=git_env
            )
            sha_result = _run_git(["git", "rev-parse", "HEAD"], cwd=cwd, env=git_env)
            return {
                "committed": True,
                "branch": branch_result.stdout.strip(),
                "sha": sha_result.stdout.strip(),
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

            try:
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
            except gh_module.GithubException as exc:
                # If PR already exists for this branch, try to find and return it
                if exc.status == 422:
                    pulls = repo_obj.get_pulls(state="open", head=f"{repo.split('/')[0]}:{branch}")
                    for existing_pr in pulls:
                        return {
                            "created": False,
                            "pr_number": existing_pr.number,
                            "pr_url": existing_pr.html_url,
                            "title": existing_pr.title,
                            "note": "PR already exists for this branch.",
                        }
                return {"error": f"Failed to create PR: {exc.data.get('message', str(exc))}"}

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
            token = ""
            token_source = "none"

            if creds:
                token = creds.get("personal_access_token") or creds.get("token") or ""
                if token:
                    token_source = "connections_db"
            if not token:
                token = os.environ.get("GITHUB_TOKEN", "")
                if token:
                    token_source = "GITHUB_TOKEN_env"

            self.logger.info("GitHub token source: %s", token_source)

            if not token:
                return {
                    "error": (
                        "No GitHub credentials found. Please add a GitHub Personal Access "
                        "Token in Settings -> Connections with 'repo' scope."
                    )
                }

            deps = SoftwareDevDeps(
                github_token=token,
                workspace_dir=workspace_dir,
                user_id=user_id or "",
            )

            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="")
            if not intent:
                return {"error": "No issue URL or instructions provided."}

            # Extract issue URL and build an explicit prompt so the LLM
            # doesn't ask the user for it again.
            issue_match = re.search(r"https?://github\.com/[^/]+/[^/]+/issues/\d+", intent)
            if issue_match:
                issue_url = issue_match.group(0)
                prompt = (
                    f"Work on this GitHub issue: {issue_url}\n"
                    f"Call `fetch_issue` with the URL above, then follow "
                    f"the full workflow to open a PR."
                )
            else:
                prompt = intent

            result = await self._get_agent().run(prompt, model=get_llm_model(), deps=deps)
            summary = str(result.output)

            # Schedule CI follow-up if a PR was opened
            await self._schedule_ci_followup(summary, task, token)

            return {"summary": summary}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("SoftwareDeveloperAgent error")
            safe_msg = _sanitize_token(str(exc), token if "token" in dir() else "")
            return {"summary": f"Software dev error: {safe_msg}", "error": safe_msg}
        finally:
            # Clean up workspace
            if workspace_dir.exists():
                shutil.rmtree(workspace_dir, ignore_errors=True)

    async def _schedule_ci_followup(
        self, summary: str, task: dict[str, Any], token: str
    ) -> None:
        """If a PR was created, schedule a follow-up to check CI status."""
        # Look for PR URL in the summary
        pr_match = re.search(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", summary)
        if not pr_match:
            return

        repo = pr_match.group(1)
        pr_number = pr_match.group(2)
        user_id = task.get("user_id", "system")

        try:
            await self.schedule_followup(
                user_id=user_id,
                delay_seconds=600,  # 10 minutes
                title=f"Check CI status for {repo}#{pr_number}",
                intent=f"check_ci_for_pr:{repo}:{pr_number}",
                agent_slug="software-dev",
            )
            self.logger.info(
                "Scheduled CI follow-up for %s#%s in 10 minutes", repo, pr_number
            )
        except Exception:
            self.logger.debug("Failed to schedule CI follow-up", exc_info=True)


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


def _build_git_env(token: str, workspace_dir: Path) -> dict[str, str]:
    """Build environment dict for git commands using GIT_ASKPASS for auth.

    Instead of embedding the PAT in clone URLs (which leaks in
    ``git remote -v`` and logs), we write a tiny helper script that
    echoes the token and point ``GIT_ASKPASS`` at it.
    """
    env = {**os.environ}
    if not token:
        return env

    askpass_script = workspace_dir / ".git-askpass"
    askpass_script.write_text(f"#!/bin/sh\necho '{token}'\n")
    askpass_script.chmod(stat.S_IRWXU)

    env["GIT_ASKPASS"] = str(askpass_script)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result


def _sanitize_token(text: str, token: str) -> str:
    """Remove the GitHub PAT from any string to prevent leakage."""
    if not token or not text:
        return text
    return text.replace(token, "***")


def _get_dir_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


_AUTH_ERROR_PATTERNS = re.compile(
    r"authentication failed|could not read username|"
    r"permission.denied|403|401|invalid credentials",
    re.IGNORECASE,
)


def _classify_git_error(returncode: int, stderr: str) -> str:
    """Return an actionable error message for common git failures."""
    if returncode == 128 and _AUTH_ERROR_PATTERNS.search(stderr):
        return (
            "GitHub authentication failed. Please verify your Personal Access Token "
            "in Settings -> Connections has the 'repo' scope and has not expired."
        )
    return f"git failed (exit {returncode}): {stderr}"
