from abc import ABC, abstractmethod

from app.config import settings


class EmailProvider(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, html: str) -> bool:
        ...


def get_email_provider() -> EmailProvider:
    if not settings.smtp_user or not settings.smtp_password:
        from app.services.email.log import LogEmailProvider

        return LogEmailProvider()

    from app.services.email.smtp import SMTPEmailProvider

    return SMTPEmailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_name=settings.smtp_from_name,
        from_email=settings.smtp_from_email,
        use_tls=settings.smtp_use_tls,
    )
