# keyboards/main_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧪 اکانت تست"),
                KeyboardButton(text="🛒 خرید اشتراک"),
            ],
            [
                KeyboardButton(text="🔁 تمدید سرویس"),
                KeyboardButton(text="👛 کیف پول / شارژ"),
            ],
            [
                KeyboardButton(text="📦 اشتراک‌های من"),
            ],
            [
                KeyboardButton(text="📚 آموزش"),
                KeyboardButton(text="🛟 پشتیبانی"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,  # کیبورد نمی‌پره بعد از انتخاب
        input_field_placeholder="یکی از گزینه‌ها رو انتخاب کن…"
    )
