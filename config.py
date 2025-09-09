# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    MONGO_URI: str
    MONGO_DB: str = "vira-vpn"
    SUPPORT_USERNAME: str = "stanwitley"
    admin_ids: list[int] = [149609494]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
