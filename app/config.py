import json

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/physioversecore"
    secret_key: str = "super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    jwt_issuer: str = "sahayatri-physio"
    jwt_audience: str = "sahayatri-physio"
    backend_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "BACKEND_PORT"),
    )
    uvicorn_reload: bool = True

    redis_url: str = "redis://localhost:6379/0"
    rate_limit_enabled: bool = True
    rate_limit_default_limit: int = 100
    rate_limit_default_window: int = 60
    rate_limit_storage_backend: str = "redis"

    cors_origins: str = '["*"]'

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Sahayatri Physio"
    smtp_from_email: str = "noreply@sahayatri.np"
    smtp_use_tls: bool = True

    otp_expire_minutes: int = 5
    otp_length: int = 6
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 120

    google_client_id: str = ""
    google_client_secret: str = ""

    upload_dir: str = "./Upload"

    # Public base URL of the Next.js frontend — used to build payment gateway
    # return/callback URLs (Khalti return_url, etc.). Must be publicly reachable
    # when gateways need to redirect the user back.
    app_public_url: str = "http://localhost:3000"

    # --- Payment Gateway: eSewa (ePay v2) ---
    esewa_env: str = "uat"
    esewa_product_code: str = "EPAYTEST"
    esewa_secret_key: str = ""
    esewa_success_url: str = "http://localhost:3000/api/webhooks/payments/esewa"
    esewa_failure_url: str = "http://localhost:3000/api/webhooks/payments/esewa"

    # --- Payment Gateway: Khalti / IME (KPG-2 Web Checkout) ---
    khalti_env: str = "test"
    khalti_secret_key: str = ""
    khalti_public_key: str = ""
    khalti_return_url: str = "http://localhost:3000/api/webhooks/payments/khalti"

    # --- Payment Gateway: ConnectIPS (NCHL) — Phase 2 ---
    connectips_env: str = "uat"
    connectips_merchant_id: str = ""
    connectips_app_id: str = ""
    connectips_app_name: str = ""
    connectips_app_password: str = ""
    connectips_pfx_path: str = ""
    connectips_pfx_password: str = ""

    class Config:
        env_file = ".env"

    @property
    def cors_origin_list(self) -> list[str]:
        return json.loads(self.cors_origins)


settings = Settings()
