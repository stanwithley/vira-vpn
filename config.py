# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    MONGO_URI: str
    MONGO_DB: str = "vira-vpn"
    SUPPORT_USERNAME: str = "stanwitley"

    # کارت به کارت
    C2C_CARD_NUMBER: str = "6037-9974-4031-4483"
    C2C_CARD_NAME: str = "به‌نام: هاتف فلاح"
    C2C_DEADLINE_MIN: int = 60

    # چند ادمین (لیست عددی chat_id)
    ADMIN_CHAT_IDS: list[int] = [149609494]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
