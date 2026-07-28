import logging

from app.services.email.base import EmailProvider

log = logging.getLogger(__name__)


class LogEmailProvider(EmailProvider):
    async def send(self, to: str, subject: str, html: str) -> bool:
        import re

        code_match = re.search(r">(\d{6})<", html)
        code = code_match.group(1) if code_match else "??????"
        log.warning("OTP %s → %s (subject: %s)", code, to, subject)
        return True
