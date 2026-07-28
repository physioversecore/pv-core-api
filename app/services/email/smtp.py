import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

from app.services.email.base import EmailProvider

logger = logging.getLogger(__name__)


class SMTPEmailProvider(EmailProvider):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_name: str,
        from_email: str,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_name = from_name
        self.from_email = from_email
        self.use_tls = use_tls

    async def send(self, to: str, subject: str, html: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.from_email, [to], msg.as_string())
            logger.info("email_sent", extra={"to": to, "subject": subject})
            return True
        except Exception:
            logger.exception("email_send_failed", extra={"to": to, "subject": subject})
            return False
