import random
import string
from datetime import datetime, timedelta, timezone

from jinja2 import Template
from prisma import Prisma

from app.config import settings
from app.services.email.dispatch import dispatch_email

OTP_TEMPLATE_PATH = "app/templates/otp_email.html"


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=settings.otp_length))


def _render_otp_email(name: str, code: str, purpose: str = "signup") -> str:
    with open(OTP_TEMPLATE_PATH) as f:
        tmpl = Template(f.read())

    if purpose == "password_reset":
        return tmpl.render(
            brand_name="Sahayatri Physio",
            tagline="Your physiotherapy recovery partner",
            title="Reset your password",
            name=name.split()[0] if name else "there",
            body_line1="We received a request to reset your password. Use the code below to proceed. This code is valid for a limited time.",
            otp_label="Your password reset code",
            otp_code=code,
            body_line2="If you didn't request a password reset, you can safely ignore this email.",
            body_line3=f"This code expires in {settings.otp_expire_minutes} minutes.",
            footer_line1="Sahayatri Physio — Home-visit physiotherapy in Nepal.",
            footer_line2="This is an automated message, please do not reply.",
        )

    return tmpl.render(
        brand_name="Sahayatri Physio",
        tagline="Your physiotherapy recovery partner",
        title="Verify your email",
        name=name.split()[0] if name else "there",
        body_line1="Use the code below to verify your email address. This code is valid for a limited time.",
        otp_label="Your verification code",
        otp_code=code,
        body_line2="If you didn't request this, you can safely ignore this email.",
        body_line3=f"This code expires in {settings.otp_expire_minutes} minutes.",
        footer_line1="Sahayatri Physio — Home-visit physiotherapy in Nepal.",
        footer_line2="This is an automated message, please do not reply.",
    )


async def send_otp_email(to: str, name: str, code: str, purpose: str = "signup") -> None:
    await dispatch_email(
        to=to,
        subject=f"Your {settings.smtp_from_name} verification code",
        html=_render_otp_email(name, code, purpose),
    )


async def create_otp(
    db: Prisma, email: str, name: str = "there", purpose: str = "signup"
) -> dict:
    now = datetime.now(timezone.utc)

    latest_unused = await db.emailverification.find_first(
        where={"email": email, "purpose": purpose, "used": False},
        order={"createdAt": "desc"},
    )

    if latest_unused:
        elapsed = (now - latest_unused.createdAt.replace(tzinfo=timezone.utc)).total_seconds()
        remaining = settings.otp_resend_cooldown_seconds - elapsed
        if remaining > 0:
            return {"created": False, "resend_after": int(remaining)}

    await db.emailverification.update_many(
        where={"email": email, "purpose": purpose, "used": False},
        data={"used": True},
    )

    code = _generate_code()
    await db.emailverification.create(
        data={
            "email": email,
            "code": code,
            "purpose": purpose,
            "expiresAt": now + timedelta(minutes=settings.otp_expire_minutes),
        }
    )

    return {
        "created": True,
        "resend_after": settings.otp_resend_cooldown_seconds,
        "to": email,
        "name": name,
        "code": code,
        "purpose": purpose,
    }


async def verify_otp(db: Prisma, email: str, code: str, purpose: str = "signup") -> bool:
    record = await db.emailverification.find_first(
        where={"email": email, "purpose": purpose, "used": False},
        order={"createdAt": "desc"},
    )

    if not record:
        return False

    if record.expiresAt < datetime.now(timezone.utc):
        return False

    if record.attempts >= settings.otp_max_attempts:
        return False

    if record.code != code:
        await db.emailverification.update(
            where={"id": record.id},
            data={"attempts": record.attempts + 1},
        )
        return False

    await db.emailverification.update(
        where={"id": record.id},
        data={"used": True},
    )
    return True
