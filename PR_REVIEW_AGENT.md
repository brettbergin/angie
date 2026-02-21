# PR Review Response Agent

An AI agent workflow for triaging and addressing pull request review feedback. This agent reads review comments from a GitHub PR, evaluates their validity, implements fixes, commits them, and replies to each comment thread with a summary and commit link.

## Purpose

Automate the tedious cycle of reading PR feedback → evaluating → fixing → committing → replying. This agent handles the full loop for each review comment, including rejecting invalid suggestions with a reasoned explanation.

## Workflow

```
1. FETCH — Retrieve all review threads from the PR
2. TRIAGE — For each comment, evaluate validity:
   a. Read the referenced file and line
   b. Understand the reviewer's concern
   c. Determine if the suggestion is correct, partially correct, or invalid
3. IMPLEMENT — For valid comments:
   a. Make the minimal code change to address the concern
   b. Verify the change compiles/passes tests
4. COMMIT — Create a single commit (or one per logical group) with all fixes
5. PUSH — Push to the PR branch
6. REPLY — For each review thread:
   - Valid & fixed: Reply with ✅, summary of what was done, and a hyperlink to the commit
   - Invalid: Reply with ⚠️ and a clear technical explanation of why the suggestion doesn't apply
7. VERIFY — Run the full test suite and build to confirm nothing is broken
```

## Input

The agent requires:

- **PR URL or number** — e.g., `https://github.com/owner/repo/pull/5` or `#5`
- **Repository access** — ability to read files, push commits, and comment via GitHub API
- **Build/test commands** — to validate changes don't break anything

## Output

For each review comment, the agent produces:

- A code fix (if valid) committed and pushed to the PR branch
- A reply on the review thread with:
  - Status indicator (✅ fixed, ⚠️ not applicable)
  - Brief summary of the change or reason for rejection
  - Link to the commit (for fixes)

## Agent Prompt

```
You are a PR Review Response Agent. Your job is to process pull request review
comments, evaluate each one, and either fix the issue or explain why the
suggestion is invalid.

For each review comment:

1. Read the file and surrounding context referenced by the comment.
2. Understand the reviewer's concern — what bug, risk, or improvement are they
   pointing out?
3. Evaluate validity:
   - Is the concern technically correct?
   - Does the suggested fix actually work in this codebase's context?
   - Are there framework-specific behaviors that invalidate the suggestion?
4. If VALID: Make the minimal fix. Prefer the reviewer's suggestion if it works,
   otherwise implement the correct solution. Verify with build/tests.
5. If INVALID: Prepare a clear, respectful technical explanation.
6. After all changes are made, create a commit with a descriptive message listing
   all addressed comments.
7. Push to the PR branch.
8. Reply to each review thread individually with the result.

Reply format for VALID fixes:
"✅ Fixed. [One sentence describing what was changed]. See [commit_sha](commit_url)."

Reply format for INVALID suggestions:
"⚠️ Not applicable. [Technical explanation of why the suggestion doesn't apply
in this context]."

Rules:
- Always run tests after making changes to verify nothing is broken.
- Group related fixes into a single commit when they touch the same concern.
- Never silently skip a comment — every thread gets a reply.
- Be respectful but technically precise when rejecting suggestions.
- If a suggestion is partially correct, implement the valid part and explain
  what was adjusted and why.
```

## Example Execution

Given a PR with 12 review comments:

| # | File | Concern | Result |
|---|------|---------|--------|
| 1 | settings/page.tsx | Missing `Intl` feature detection | ✅ Added fallback |
| 2 | settings/page.tsx | Redundant `refreshUser()` call | ✅ Removed |
| 3 | teams/page.tsx | Optimistic delete race condition | ✅ Moved update after API |
| 4 | workflows/page.tsx | `useEffect` exhaustive-deps | ✅ Added `useCallback` |
| 5 | teams/page.tsx | `useEffect` exhaustive-deps | ✅ Added `useCallback` |
| 6 | prompts.py | `unlink()` TOCTOU race | ✅ Used `missing_ok=True` |
| 7 | chat/page.tsx | Imperative DOM manipulation | ✅ Refactored to `useRef` |
| 8 | teams/page.tsx | Unreliable `onBlur` dropdown | ✅ Click-outside listener |
| 9 | chat/page.tsx | Missing XSS sanitization | ✅ Added `rehype-sanitize` |
| 10 | team.py | `default=list` mutable default | ⚠️ Invalid — SQLAlchemy callable |
| 11 | migration.py | `existing_type=sa.JSON()` syntax | ✅ Removed parentheses |
| 12 | chat.py | Missing type annotation | ✅ Added `User` type hint |

Result: 11 fixes committed, 1 rejected with explanation. 519 tests passing.

## Integration

This agent can be integrated into any AI tool that supports:

- GitHub API access (read PR comments, push commits, post replies)
- File system access (read/edit source files)
- Shell access (run build/test commands)

### As a GitHub Actions Workflow

Trigger on `pull_request_review` events to automatically process new reviews.

### As a CLI Agent

```bash
# Example invocation
agent run pr-review --pr 5 --repo owner/repo --auto-fix
```

### As an MCP Tool

Expose as an MCP server with tools for:
- `fetch_pr_reviews(pr_number)` — get all review threads
- `evaluate_comment(thread_id)` — assess validity
- `fix_and_reply(thread_id, fix_description)` — implement, commit, reply
