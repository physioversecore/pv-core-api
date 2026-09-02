from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from datetime import datetime, timezone
from prisma import Prisma
from prisma.enums import Role

from app import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    ResetPasswordRequest,
    SendOtpRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
    VerifyOtpRequest,
    authenticate_user,
    bump_token_version,
    create_access_token,
    create_therapist_signup,
    create_user,
    find_or_create_google_user,
    generate_referral_code,
    generate_temp_password,
    get_current_user,
    get_current_user_lenient,
    get_db,
    hash_password,
    set_temporary_password,
    update_user,
    verify_google_credential,
    verify_password,
)
from app.services.email.notifications import send_application_received_email
from app.services.otp import create_otp, send_otp_email, verify_otp

router = APIRouter(prefix="/auth", tags=["Auth"])


async def _user_with_photo(db: Prisma, user) -> UserResponse:
    """Serialize a user, attaching their profile photo (first mediaUrls entry)
    so avatars load from the auth session across the app."""
    data = UserResponse.model_validate(user).model_dump()
    if user.role == "THERAPIST":
        therapist = await db.therapist.find_unique(where={"userId": user.id})
        media_urls = getattr(therapist, "mediaUrls", None)
        if therapist and isinstance(media_urls, str) and media_urls.strip():
            data["photo"] = media_urls.split(",")[0].strip()
    return UserResponse(**data)


@router.post("/send-otp")
async def send_verification_otp(
    data: SendOtpRequest,
    background_tasks: BackgroundTasks,
    db: Prisma = Depends(get_db),
):
    existing = await db.user.find_unique(where={"email": data.email})
    if existing:
        # A registered email cannot request a signup code. Any signup flow for
        # this email is already complete — the user should log in instead.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    result = await create_otp(db, email=data.email, name=data.name, purpose="signup")
    if not result["created"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {result['resend_after']} seconds before requesting a new code",
        )
    # Email delivery happens in the background so a slow SMTP server never
    # blocks the signup flow.
    background_tasks.add_task(
        send_otp_email,
        result["to"],
        result["name"],
        result["code"],
        result["purpose"],
    )
    return {"message": "OTP sent successfully", "resend_after": result["resend_after"]}


@router.post("/send-login-otp")
async def send_login_otp(
    data: SendOtpRequest,
    background_tasks: BackgroundTasks,
    db: Prisma = Depends(get_db),
):
    existing = await db.user.find_unique(where={"email": data.email})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email",
        )

    result = await create_otp(db, email=data.email, name=data.name or existing.name, purpose="login")
    if not result["created"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {result['resend_after']} seconds before requesting a new code",
        )
    background_tasks.add_task(
        send_otp_email,
        result["to"],
        result["name"],
        result["code"],
        result["purpose"],
    )
    return {"message": "OTP sent successfully", "resend_after": result["resend_after"]}


@router.post("/login-otp", response_model=TokenResponse)
async def login_with_otp(data: VerifyOtpRequest, db: Prisma = Depends(get_db)):
    valid = await verify_otp(db, email=data.email, code=data.code, purpose="login")
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    user = await db.user.find_unique(where={"email": data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email",
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

    token = create_access_token(
        user.id, role=user.role, token_version=user.tokenVersion or 0
    )
    return TokenResponse(
        access_token=token,
        user=await _user_with_photo(db, user),
    )


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
async def signup(
    data: SignupRequest,
    background_tasks: BackgroundTasks,
    db: Prisma = Depends(get_db),
):
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
        if not payload.get("password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required",
            )
        user_data["referralCode"] = generate_referral_code()

    if role_val == "THERAPIST":
        user_data["status"] = "PENDING"
        # Therapists apply without a password. Store a random placeholder that is
        # never emailed — the admin approval step replaces it with a real
        # temporary password that is emailed to the therapist.
        if not payload.get("password"):
            user_data["password"] = generate_temp_password()
            user_data["mustChangePassword"] = True

    user = await create_user(db, user_data)

    if role_val == "THERAPIST":
        await create_therapist_signup(db, user, payload)

    # Therapist applications require admin approval before they can log in to
    # normal pages, but they need a token to complete onboarding.
    if role_val == "THERAPIST":
        background_tasks.add_task(send_application_received_email, user.email, user.name)
        token = create_access_token(
        user.id, role=user.role, token_version=user.tokenVersion or 0
    )
        return TokenResponse(
            access_token=token,
            user=await _user_with_photo(db, user),
        )

    token = create_access_token(
        user.id, role=user.role, token_version=user.tokenVersion or 0
    )

    return TokenResponse(
        access_token=token,
        user=await _user_with_photo(db, user),
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
    token = create_access_token(
        user.id, role=user.role, token_version=user.tokenVersion or 0
    )
    return TokenResponse(
        access_token=token,
        user=await _user_with_photo(db, user),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user=Depends(get_current_user_lenient),
    db: Prisma = Depends(get_db),
):
    return await _user_with_photo(db, current_user)


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    data: UserUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    user = await update_user(db, current_user.id, data.model_dump(exclude_none=True))
    return await _user_with_photo(db, user)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Prisma = Depends(get_db),
):
    existing = await db.user.find_unique(where={"email": data.email})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email",
        )

    result = await create_otp(
        db, email=data.email, name=data.name or existing.name, purpose="password_reset"
    )
    if not result["created"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {result['resend_after']} seconds before requesting a new code",
        )
    background_tasks.add_task(
        send_otp_email,
        result["to"],
        result["name"],
        result["code"],
        result["purpose"],
    )
    return {"message": "OTP sent successfully", "resend_after": result["resend_after"]}


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
    await update_user(
        db,
        current_user.id,
        {"password": hash_password(data.new_password), "mustChangePassword": False},
    )


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: DeleteAccountRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if data.password:
        if not verify_password(data.password, current_user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
    await db.user.delete(where={"id": current_user.id})


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    return None


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all_devices(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    await bump_token_version(db, current_user.id)
    return None


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    data: GoogleAuthRequest,
    background_tasks: BackgroundTasks,
    db: Prisma = Depends(get_db),
):
    google_user = await verify_google_credential(data.credential)
    if not google_user or not google_user.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        )

    try:
        user, created = await find_or_create_google_user(db, google_user, data.role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
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

    token = create_access_token(
        user.id, role=user.role, token_version=user.tokenVersion or 0
    )
    return TokenResponse(
        access_token=token,
        user=await _user_with_photo(db, user),
    )


@router.post("/check-email")
async def check_email(data: dict, db: Prisma = Depends(get_db)):
    email = data.get("email", "")
    user = await db.user.find_unique(where={"email": email})
    return {"exists": user is not None, "role": user.role.lower() if user else None}
