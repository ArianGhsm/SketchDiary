from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    DB_URL: str = "sqlite+aiosqlite:////data/bot.db"  # default for Fly Volume
    LOG_LEVEL: str = "INFO"

    OWNER_STUDENT_ID: str = "40211272003"


settings = Settings()
