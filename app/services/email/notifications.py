from jinja2 import Template

from app.config import settings
from app.services.email import get_email_provider

APPLICATION_RECEIVED_TEMPLATE_PATH = "app/templates/application_received.html"


def _render_application_received_email(name: str) -> str:
    with open(APPLICATION_RECEIVED_TEMPLATE_PATH) as f:
        tmpl = Template(f.read())

    return tmpl.render(
        brand_name="Sahayatri Physio",
        tagline="Your physiotherapy recovery partner",
        title="Application received",
        name=name.split()[0] if name else "there",
        body_line1="Thank you for applying to join Sahayatri Physio as a therapist. Your application and supporting documents have been received.",
        status_label="Application status",
        status_title="Under review",
        body_line2="Our team is reviewing your application. We typically verify applications within 24 hours.",
        body_line3="Once your application is approved, you will be able to log in and start using your therapist dashboard.",
        body_line4="If you have any questions, please contact our support team.",
        footer_line1="Sahayatri Physio — Home-visit physiotherapy in Nepal.",
        footer_line2="This is an automated message, please do not reply.",
    )


async def send_application_received_email(email: str, name: str = "") -> bool:
    provider = get_email_provider()
    return await provider.send(
        to=email,
        subject=f"Your {settings.smtp_from_name} application is under review",
        html=_render_application_received_email(name),
    )
