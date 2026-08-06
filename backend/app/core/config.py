from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "eve-quartermaster"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://eve:eve@postgres:5432/eve_quartermaster"
    redis_url: str = "redis://redis:6379/0"
    eve_sso_client_id: str = ""
    eve_sso_client_secret: str = ""
    token_encryption_key: str = ""
    frontend_url: str = "http://localhost:5173"
    eve_sso_callback_url: str = "http://localhost:8000/api/esi/auth/callback"
    esi_compatibility_date: str = "2026-07-22"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,https://eqm.easyduneadmin.app"
    auth_secret_key: str = "dev-change-me"
    access_token_minutes: int = 720
    remember_me_days: int = 30
    sde_source_path: str = "/sde"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
