from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app.database import get_db
from app.deps import get_current_user
from app.models.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import authenticate_user, create_access_token, create_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, db: Prisma = Depends(get_db)):
    existing = await db.user.find_unique(where={"email": data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user_data = data.model_dump(exclude={"password"})
    user_data["role"] = getattr(Role, data.role.upper(), Role.PATIENT)
    user_data["password"] = data.password

    user = await create_user(db, user_data)
    token = create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: Prisma = Depends(get_db)):
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    # In a stateless JWT authentication system, logout is typically handled on the client side
    # by deleting the token. However, if you want to implement server-side token invalidation,
    # you would need to maintain a token blacklist or use a token revocation strategy.
    return None