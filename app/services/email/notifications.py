from jinja2 import Template

from app.config import settings
from app.services.email.dispatch import dispatch_email

APPLICATION_RECEIVED_TEMPLATE_PATH = "app/templates/application_received.html"
ACCOUNT_VERIFIED_TEMPLATE_PATH = "app/templates/account_verified.html"
APPLICATION_REJECTED_TEMPLATE_PATH = "app/templates/application_rejected.html"


def _first_name(name: str) -> str:
    return name.split()[0] if name else "there"


def _render_application_received_email(name: str) -> str:
    with open(APPLICATION_RECEIVED_TEMPLATE_PATH) as f:
        tmpl = Template(f.read())

    return tmpl.render(
        brand_name="Sahayatri Physio",
        tagline="Your physiotherapy recovery partner",
        title="Application received",
        name=_first_name(name),
        body_line1="Thank you for applying to join Sahayatri Physio as a therapist. Your application and supporting documents have been received.",
        status_label="Application status",
        status_title="Under review",
        body_line2="Our team is reviewing your application. We typically verify applications within 24 hours.",
        body_line3="Once your application is approved, you will be able to log in and start using your therapist dashboard.",
        body_line4="If you have any questions, please contact our support team.",
        footer_line1="Sahayatri Physio — Home-visit physiotherapy in Nepal.",
        footer_line2="This is an automated message, please do not reply.",
    )


def _render_account_verified_email(
    name: str, username: str = "", temp_password: str | None = None
) -> str:
    with open(ACCOUNT_VERIFIED_TEMPLATE_PATH) as f:
        tmpl = Template(f.read())

    if temp_password:
        title = "Your account has been approved"
        status_title = "Approved"
        body_line2 = (
            f"Congratulations! Your therapist account on Sahayatri Physio has been approved. "
            f"Use the temporary password below to log in for the first time."
        )
        body_line3 = "You will be asked to set your own password right after your first login."
    else:
        title = "Your account has been verified"
        status_title = "Verified"
        body_line2 = "Congratulations! Your therapist account on Sahayatri Physio has been verified."
        body_line3 = "You can now log in to your therapist dashboard with the email address and password you registered with."

    return tmpl.render(
        brand_name="Sahayatri Physio",
        tagline="Your physiotherapy recovery partner",
        title=title,
        name=_first_name(name),
        body_line1="Congratulations! Your therapist account on Sahayatri Physio is ready to use.",
        status_label="Account status",
        status_title=status_title,
        body_line2=body_line2,
        body_line3=body_line3,
        body_line4="If you have any questions, please contact our support team.",
        username=username,
        temp_password=temp_password or "",
        footer_line1="Sahayatri Physio — Home-visit physiotherapy in Nepal.",
        footer_line2="This is an automated message, please do not reply.",
    )


def _render_application_rejected_email(name: str, reason: str) -> str:
    with open(APPLICATION_REJECTED_TEMPLATE_PATH) as f:
        tmpl = Template(f.read())

    return tmpl.render(
        brand_name="Sahayatri Physio",
        tagline="Your physiotherapy recovery partner",
        title="Update on your application",
        name=_first_name(name),
        body_line1="Thank you for applying to join Sahayatri Physio as a therapist. After careful review, we were unable to verify your application at this time.",
        reason_label="Reason(s)",
        reason_text=reason or "Your application did not meet our verification requirements.",
        body_line2="If you believe this is a mistake, or you would like to reapply with updated documents, please contact our support team.",
        body_line3="You can reapply once the issue is resolved — we would love to have you on board.",
        body_line4="If you have any questions, please contact our support team.",
        footer_line1="Sahayatri Physio — Home-visit physiotherapy in Nepal.",
        footer_line2="This is an automated message, please do not reply.",
    )


async def send_application_received_email(email: str, name: str = "") -> None:
    await dispatch_email(
        to=email,
        subject=f"Your {settings.smtp_from_name} application is under review",
        html=_render_application_received_email(name),
    )


async def send_account_verified_email(
    email: str,
    name: str = "",
    temp_password: str | None = None,
    username: str = "",
) -> None:
    await dispatch_email(
        to=email,
        subject=f"Your {settings.smtp_from_name} account has been approved",
        html=_render_account_verified_email(name, username, temp_password),
    )


async def send_application_rejected_email(email: str, name: str = "", reason: str = "") -> None:
    await dispatch_email(
        to=email,
        subject=f"Update on your {settings.smtp_from_name} application",
        html=_render_application_rejected_email(name, reason),
    )
