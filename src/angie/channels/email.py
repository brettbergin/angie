"""Email channel adapter (SMTP send / IMAP receive)."""

from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any

from angie.channels.base import BaseChannel
from angie.config import get_settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60  # seconds between IMAP inbox checks


class EmailChannel(BaseChannel):
    channel_type = "email"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._poll_task: asyncio.Task | None = None

    async def start(self) -> None:
        s = self.settings
        logger.info("Email channel ready (SMTP: %s)", s.email_smtp_host)
        if s.email_imap_host and s.email_username:
            self._poll_task = asyncio.create_task(self._poll_inbox())

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()

    async def _poll_inbox(self) -> None:
        """Periodically check IMAP inbox for new messages addressed to Angie."""
        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._check_inbox)
            except Exception as exc:
                logger.warning("Email IMAP poll error: %s", exc)
            await asyncio.sleep(POLL_INTERVAL)

    def _check_inbox(self) -> None:
        s = self.settings
        try:
            conn = imaplib.IMAP4_SSL(s.email_imap_host, s.email_imap_port)
            conn.login(s.email_username, s.email_password or "")
            conn.select("INBOX")
            _, msg_ids = conn.search(None, "UNSEEN")
            for mid in (msg_ids[0] or b"").split():
                _, data = conn.fetch(mid, "(RFC822)")
                raw = data[0][1] if data and data[0] else None
                if not raw:
                    continue
                msg = email_lib.message_from_bytes(raw)
                sender = email_lib.utils.parseaddr(msg.get("From", ""))[1]
                subject = msg.get("Subject", "")
                body = self._extract_body(msg)
                logger.info("Email from %s: %s", sender, subject)
                # Fire event (sync → schedule on event loop)
                asyncio.run_coroutine_threadsafe(
                    self._dispatch_event(sender, subject, body),
                    asyncio.get_event_loop(),
                )
                # Mark as seen
                conn.store(mid, "+FLAGS", "\\Seen")
            conn.logout()
        except Exception as exc:
            logger.warning("IMAP error: %s", exc)

    def _extract_body(self, msg: email_lib.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
        return (
            msg.get_payload(decode=True).decode("utf-8", errors="replace")
            if isinstance(msg.get_payload(), bytes)
            else str(msg.get_payload())
        )

    async def _dispatch_event(self, sender: str, subject: str, body: str) -> None:
        from angie.core.events import AngieEvent, router
        from angie.models.event import EventType

        event = AngieEvent(
            type=EventType.CHANNEL_MESSAGE,
            user_id=sender,
            payload={"text": body.strip()[:2000], "subject": subject, "from": sender},
            source_channel="email",
        )
        await router.dispatch(event)

    async def send(
        self, user_id: str, text: str, subject: str = "Message from Angie", **kwargs: Any
    ) -> None:
        s = self.settings
        if not s.email_smtp_host or not s.email_username:
            logger.warning("Email channel not configured")
            return

        msg = MIMEText(text)
        msg["Subject"] = subject
        msg["From"] = s.email_username
        msg["To"] = user_id

        await asyncio.get_event_loop().run_in_executor(None, self._smtp_send, msg, user_id)

    def _smtp_send(self, msg: MIMEText, to: str) -> None:
        s = self.settings
        with smtplib.SMTP(s.email_smtp_host, s.email_smtp_port) as server:
            server.starttls()
            server.login(s.email_username, s.email_password or "")
            server.sendmail(s.email_username, to, msg.as_string())

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, text, subject="Angie needs your attention", **kwargs)
