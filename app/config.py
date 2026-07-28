import json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/physioversecore"
    secret_key: str = "super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    backend_port: int = 8000
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

    class Config:
        env_file = ".env"

    @property
    def cors_origin_list(self) -> list[str]:
        return json.loads(self.cors_origins)


settings = Settings()
