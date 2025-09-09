# handlers/start.py
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from db.mongo_crud import get_or_create_user
from keyboards.main_menu import main_menu   # ← همین کیبوردی که داری

router = Router()

@router.message(CommandStart())
async def start_cmd(m: Message):
    # اگر deep-link داشت (مثل /start promo123)
    args = m.text.split(maxsplit=1)[1] if (m.text and " " in m.text) else None

    # ساخت/آپدیت کاربر در دیتابیس
    await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name
    )

    # متن خوش‌آمد
    text = "سلام 👋\nبه بات خوش اومدی!"
    if args:
        text += f"\nکدت رو گرفتم: <code>{args}</code>"

    # ارسال پیام + کیبورد اصلی
    await m.answer(text, parse_mode="HTML", reply_markup=main_menu())
