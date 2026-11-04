from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables; no secrets in code."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./marketpulse.db"
    jwt_secret: str  # required: no default on purpose
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "reports@marketpulse.local"
    email_dev_mode: bool = True  # log emails to EmailLog instead of sending
    scraper_user_agent: str = "MarketPulseBot/1.0 (+contact: set-in-env)"
    scraper_min_delay: float = 1.0
    scraper_max_delay: float = 3.5
    rate_limit: str = "120/minute"
    reports_dir: str = "./reports"
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
