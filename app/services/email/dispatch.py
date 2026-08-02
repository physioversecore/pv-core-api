"""Fire-and-forget email dispatch.

Emails are secondary to the API's main flow (signup, OTP, admin actions).
Sending is dispatched through FastAPI ``BackgroundTasks`` and must never
block or fail the request, so every send is wrapped here and failures are
only logged.
"""

import logging

from app.services.email import get_email_provider

logger = logging.getLogger(__name__)


async def dispatch_email(to: str, subject: str, html: str) -> None:
    try:
        provider = get_email_provider()
        await provider.send(to=to, subject=subject, html=html)
    except Exception:
        logger.exception(
            "Background email dispatch failed",
            extra={"to": to, "subject": subject},
        )
