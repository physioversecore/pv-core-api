from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    ChangePasswordRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
    authenticate_user,
    create_access_token,
    create_user,
    generate_referral_code,
    get_current_user,
    get_db,
    hash_password,
    update_user,
    verify_password,
)

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

    role_val = data.role.upper()
    if role_val == "PATIENT":
        user_data["referralCode"] = generate_referral_code()

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


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    data: UserUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    user = await update_user(db, current_user.id, data.model_dump(exclude_none=True))
    return UserResponse.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    await update_user(db, current_user.id, {"password": hash_password(data.new_password)})


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    return None
