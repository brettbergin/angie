"""Email channel adapter (SMTP send / IMAP receive)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any

from angie.channels.base import BaseChannel
from angie.config import get_settings

logger = logging.getLogger(__name__)


class EmailChannel(BaseChannel):
    channel_type = "email"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def start(self) -> None:
        logger.info("Email channel ready (SMTP: %s)", self.settings.email_smtp_host)

    async def stop(self) -> None:
        pass

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
        msg["To"] = user_id  # user_id is treated as the email address here

        with smtplib.SMTP(s.email_smtp_host, s.email_smtp_port) as server:
            server.starttls()
            server.login(s.email_username, s.email_password or "")
            server.sendmail(s.email_username, user_id, msg.as_string())

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, text, subject="Angie needs your attention", **kwargs)
