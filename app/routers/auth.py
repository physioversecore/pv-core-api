from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from prisma import Prisma
from prisma.enums import Role

from app import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SendOtpRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
    VerifyOtpRequest,
    authenticate_user,
    create_access_token,
    create_therapist_signup,
    create_user,
    generate_referral_code,
    get_current_user,
    get_db,
    hash_password,
    update_user,
    verify_password,
)
from app.services.email.notifications import send_application_received_email
from app.services.otp import send_otp, verify_otp

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/send-otp")
async def send_verification_otp(data: SendOtpRequest, db: Prisma = Depends(get_db)):
    existing = await db.user.find_unique(where={"email": data.email})
    if existing:
        # A registered email cannot request a signup code. Any signup flow for
        # this email is already complete — the user should log in instead.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    sent, resend_after = await send_otp(db, email=data.email, name=data.name, purpose="signup")
    if not sent and resend_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {resend_after} seconds before requesting a new code",
        )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email. Please try again.",
        )
    return {"message": "OTP sent successfully", "resend_after": resend_after}


@router.post("/verify-otp")
async def verify_email_otp(data: VerifyOtpRequest, db: Prisma = Depends(get_db)):
    valid = await verify_otp(db, email=data.email, code=data.code, purpose=data.purpose)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )
    return {"verified": True}


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, db: Prisma = Depends(get_db)):
    existing = await db.user.find_unique(where={"email": data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    last_otp = await db.emailverification.find_first(
        where={"email": data.email, "purpose": "signup", "used": True},
        order={"createdAt": "desc"},
    )
    if not last_otp or last_otp.expiresAt < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified. Please verify your email first.",
        )

    payload = data.model_dump()

    user_data = {
        "name": payload["name"],
        "email": payload["email"],
        "password": payload["password"],
        "role": getattr(Role, data.role.upper(), Role.PATIENT),
        "city": payload.get("city"),
        "phone": payload.get("phone"),
        "specialty": payload.get("specialty"),
    }

    role_val = data.role.upper()
    if role_val == "PATIENT":
        user_data["referralCode"] = generate_referral_code()

    if role_val == "THERAPIST":
        user_data["status"] = "PENDING"

    user = await create_user(db, user_data)

    if role_val == "THERAPIST":
        await create_therapist_signup(db, user, payload)

    # Therapist applications require admin approval before they can log in.
    # Do not issue a token until the admin sets their status to APPROVED.
    if role_val == "THERAPIST":
        try:
            await send_application_received_email(user.email, user.name)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Failed to send application-received email to %s", user.email
            )
        return TokenResponse(
            access_token=None,
            user=UserResponse.model_validate(user),
        )

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
    if user.role == "THERAPIST" and user.status != "APPROVED":
        detail = (
            "Your application is under review. You will be able to log in once it is approved."
            if user.status == "PENDING"
            else "Your application was not approved. Please contact support."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
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


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Prisma = Depends(get_db)):
    existing = await db.user.find_unique(where={"email": data.email})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email",
        )

    sent, resend_after = await send_otp(db, email=data.email, name=data.name or existing.name, purpose="password_reset")
    if not sent and resend_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {resend_after} seconds before requesting a new code",
        )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email. Please try again.",
        )
    return {"message": "OTP sent successfully", "resend_after": resend_after}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: ResetPasswordRequest, db: Prisma = Depends(get_db)):
    existing = await db.user.find_unique(where={"email": data.email})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email",
        )

    last_otp = await db.emailverification.find_first(
        where={"email": data.email, "purpose": "password_reset", "used": True},
        order={"createdAt": "desc"},
    )
    if not last_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified. Please verify your email first.",
        )

    await update_user(db, existing.id, {"password": hash_password(data.new_password)})


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
