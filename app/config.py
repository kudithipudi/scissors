"""Application configuration management (pydantic-settings)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Rock Paper Scissors"
    DEBUG: bool = False
    ROOT_PATH: str = ""

    # Security / sessions
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_MAX_AGE: int = 60 * 60 * 24  # 24 hours

    # Database
    DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "scissors.db")

    # Admin
    ADMIN_PASSWORD: str = "admin"

    # Optional "powered by" / operator link shown in the header and footer.
    # Leave blank to omit it entirely.
    SITE_LINK_URL: str = ""
    SITE_LINK_LABEL: str = ""

    # Game configuration
    GAME_TIMEOUT_MINUTES: int = 2
    MAX_GAMES_PER_IP_PER_HOUR: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 3600
    SHAKE_THRESHOLD: int = 15  # m/s^2
    REQUIRED_SHAKES: int = 3
    SHAKE_TIMEOUT_MS: int = 1000

    # QR code configuration
    QR_BOX_SIZE: int = 10
    QR_BORDER: int = 4

    # Logging
    LOG_LEVEL: str = "info"


settings = Settings()
