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

    class Config:
        env_file = ".env"


settings = Settings()
