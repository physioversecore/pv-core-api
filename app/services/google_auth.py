from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from prisma import Prisma
from prisma.enums import Role

from app.config import settings


async def verify_google_credential(credential: str) -> dict:
    """Verify a Google ID token and return the decoded payload."""
    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
        return {
            "email": idinfo.get("email", ""),
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture"),
            "google_id": idinfo.get("sub"),
        }
    except Exception:
        return {}


async def find_or_create_google_user(db: Prisma, google_user: dict, role: str = "PATIENT"):
    """Find existing user by email or create a new one from Google OAuth data.

    Returns (user, created) tuple.
    """
    email = google_user["email"]
    if not email:
        raise ValueError("Google account has no email")

    existing = await db.user.find_unique(where={"email": email})
    if existing:
        return existing, False

    import secrets
    temp_password = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%") for _ in range(16))

    from app.services.auth import hash_password, generate_referral_code

    user_data = {
        "name": google_user.get("name") or email.split("@")[0],
        "email": email,
        "password": hash_password(temp_password),
        "role": getattr(Role, role.upper(), Role.PATIENT),
        "status": "APPROVED",
    }

    if role.upper() == "PATIENT":
        user_data["referralCode"] = generate_referral_code()

    user = await db.user.create(data=user_data)
    return user, True
