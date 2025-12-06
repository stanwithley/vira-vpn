# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    MONGO_URI: str
    MONGO_DB: str = "vira-vpn"
    SUPPORT_USERNAME: str = "viravpnsupport"

    # تنظیمات پرداخت
    C2C_CARD_NUMBER: str = "6219861976330067"
    C2C_CARD_NAME: str = "به‌نام: هاتف فلاح"
    C2C_DEADLINE_MIN: int = 60

    # لیست ادمین‌ها
    ADMIN_CHAT_IDS: list[int] = [7414949914]

    # === تنظیمات اتصال به پنل (اصلاح شده با مسیر امن) ===
    # آدرس لوکال + پورت + مسیر امنی که نخواستی پاک کنی
    # این خط را دقیقاً جایگزین کنید (کپی/پیست کنید تا تایپ اشتباه نشود)
    PANEL_URL: str = "http://193.180.211.230:54321/cWrhkR40LuKobweVYO"

    PANEL_USERNAME: str = "hatef"  # یوزرنیم ورود به پنل
    PANEL_PASSWORD: str = "hatef1381"  # رمز ورود به پنل (اگه عوض کردی اینجا هم عوض کن)

    # آیدی اولین ورودی (Inbound) که ساختی معمولاً 1 هست
    INBOUND_ID: int = 1

    # اطلاعات سرور برای نمایش در لینک (اینجا آی‌پی اصلی رو می‌ذاریم)
    XRAY_DOMAIN: str = "193.180.211.230"
    XRAY_PORT: int = 8081
    XRAY_WS_PATH: str = "/ws8081"
    XRAY_SECURITY: str = "none"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()