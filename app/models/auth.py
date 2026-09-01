from pydantic import BaseModel, EmailStr, Field


class VerificationDoc(BaseModel):
    documentType: str = Field(..., max_length=64)
    url: str
    fileName: str | None = None
    fileSize: int | None = None


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str | None = None
    role: str = "PATIENT"
    city: str | None = None
    phone: str | None = None
    specialty: str | None = None
    gender: str | None = None
    license: str | None = None
    experience: int | None = None
    fee: float | None = None
    bio: str | None = None
    documents: list[VerificationDoc] | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    city: str | None = None
    phone: str | None = None
    specialty: str | None = None
    status: str
    photo: str | None = None
    mustChangePassword: bool = False

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    phone: str | None = None
    specialty: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str | None = None


class SendOtpRequest(BaseModel):
    email: EmailStr
    name: str = ""


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str
    purpose: str = "signup"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    name: str = ""


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str
