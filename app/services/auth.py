from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext
from prisma import Prisma

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


async def create_user(db: Prisma, data: dict) -> dict:
    data["password"] = hash_password(data["password"])
    user = await db.user.create(data=data)
    return user


async def create_therapist_signup(db: Prisma, user, data: dict) -> dict:
    """Create the Therapist profile + Verification records for a self-signup
    therapist. Runs after the User row exists so the admin can review the
    uploaded documents and filled-in credentials."""
    therapist = await db.therapist.create(
        data={
            "userId": user.id,
            "name": data.get("name") or user.name,
            "specialty": data.get("specialty") or user.specialty or "General",
            "city": data.get("city") or user.city or "",
            "gender": data.get("gender") or "Other",
            "licenseNumber": data.get("license"),
            "price": float(data.get("fee") or 0),
            "experience": int(data.get("experience") or 0),
            "bio": data.get("bio") or "",
        }
    )

    documents = data.get("documents") or []
    for doc in documents:
        await db.verification.create(
            data={
                "therapistId": therapist.id,
                "documentType": doc.get("documentType") or "Other document",
                "documentUrl": doc.get("url"),
                "fileName": doc.get("fileName"),
                "fileSize": doc.get("fileSize"),
                "status": "Pending review",
                "reportedBy": "Self-signup",
                "phone": data.get("phone"),
            }
        )

    return therapist


async def authenticate_user(db: Prisma, email: str, password: str):
    user = await db.user.find_unique(where={"email": email})
    if not user or not verify_password(password, user.password):
        return None
    return user


async def update_user(db: Prisma, user_id: str, data: dict):
    return await db.user.update(where={"id": user_id}, data=data)
