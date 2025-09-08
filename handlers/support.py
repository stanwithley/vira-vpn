# handlers/support.py
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings
from utils.locale import rtl

router = Router()

def support_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("گفتگو در تلگرام"), url=f"https://t.me/{settings.SUPPORT_USERNAME}")
    kb.adjust(1)
    return kb.as_markup()

@router.message(F.text == "🛟 پشتیبانی")
async def support_handler(m: types.Message):
    await m.answer(
        rtl("🛟 پشتیبانی: هر سوالی داری می‌تونی از طریق دکمهٔ زیر مستقیماً پیام بده."),
        reply_markup=support_kb()
    )
