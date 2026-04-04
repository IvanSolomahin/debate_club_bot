# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./bot.db"
    ADMIN_IDS: list[int] = []
    TIMEZONE: str = "Europe/Moscow"
    REMINDER_HOURS: list[int] = [24, 1]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]
