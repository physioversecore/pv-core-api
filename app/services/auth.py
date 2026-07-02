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


async def authenticate_user(db: Prisma, email: str, password: str):
    user = await db.user.find_unique(where={"email": email})
    if not user or not verify_password(password, user.password):
        return None
    return user
