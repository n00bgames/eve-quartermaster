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
    killboard_enabled_default: bool = True
    killboard_sync_period_hours_default: int = 6
    killboard_lookback_days_default: int = 90
    killboard_request_delay_seconds_default: float = 1.0
    killboard_max_pages_default: int = 10
    eqm_pi_engine: str = "python"
    eqm_fitting_engine: str = "python"
    eqm_fitting_stats_engine: str = "rust"
    eqm_analytics_engine: str = "rust"
    eqm_bounty_analytics_engine: str = "rust"
    eqm_jump_route_engine: str = "rust"
    eqm_settlement_math_engine: str = "rust"
    eqm_killboard_analytics_engine: str = "rust"
    eqm_srp_analytics_engine: str = "rust"
    eqm_core_binary: str = "/usr/local/bin/eqm-core"
    eqm_core_timeout_seconds: float = 5.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
