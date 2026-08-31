import logging

from app.services.email.base import EmailProvider

log = logging.getLogger(__name__)


class LogEmailProvider(EmailProvider):
    async def send(self, to: str, subject: str, html: str) -> bool:
        import re

        # The template puts the code on its own indented line, so the digits
        # are never flush against the tags -- without \s* this never matched
        # and every dev-console OTP printed as "??????".
        code_match = re.search(r">\s*(\d{4,8})\s*<", html)
        code = code_match.group(1) if code_match else "??????"
        # ASCII arrow: a Windows console using cp1252 raises
        # UnicodeEncodeError on U+2192 and loses the whole line.
        log.warning("OTP %s -> %s (subject: %s)", code, to, subject)
        return True
