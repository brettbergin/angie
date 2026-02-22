"""Context-aware email reply drafting agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class EmailCorrespondenceAgent(BaseAgent):
    name: ClassVar[str] = "EmailCorrespondenceAgent"
    slug: ClassVar[str] = "email-correspondence"
    category: ClassVar[str] = "Communication Agents"
    description: ClassVar[str] = "Context-aware email reply drafting."
    capabilities: ClassVar[list[str]] = [
        "reply email",
        "draft email",
        "respond to email",
        "email reply",
        "compose email",
    ]
    instructions: ClassVar[str] = (
        "You draft context-aware email replies using the LLM.\n\n"
        "Available tools:\n"
        "- send_email_reply: Send a drafted reply via Gmail. Requires to, subject, and body.\n\n"
        "When drafting a reply, consider the original email body, any additional context "
        "provided, and the requested tone (default: professional). The draft is generated "
        "by the LLM and can optionally be sent via the GmailAgent."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        async def send_email_reply(to: str, subject: str, body: str) -> dict:
            """Send a drafted email reply via Gmail."""
            from angie.agents.email.gmail import GmailAgent

            gmail = GmailAgent()
            return await gmail.execute(
                {
                    "input_data": {
                        "intent": f"send email to {to} with subject '{subject}' and body: {body}"
                    }
                }
            )

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model, is_llm_configured

        if not is_llm_configured():
            return {"error": "LLM not configured — set GITHUB_TOKEN or OPENAI_API_KEY"}

        data = task.get("input_data", {})
        email_body = data.get("email_body", "")
        context = data.get("context", "")
        tone = data.get("tone", "professional")

        if email_body:
            intent = (
                f"Draft a {tone} email reply to the following email:\n\n"
                f"{email_body}\n\nAdditional context: {context}"
            )
        else:
            intent = self._extract_intent(task, fallback="draft an email reply")

        self.logger.info("EmailCorrespondenceAgent intent=%r", intent[:80])
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"draft": str(result.output), "tone": tone}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("EmailCorrespondenceAgent error")
            return {"error": str(exc)}

    async def ask_llm(
        self,
        prompt: str,
        system: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Kept for backward-compatibility — delegates to the base implementation."""
        return await super().ask_llm(prompt, system=system, user_id=user_id)
