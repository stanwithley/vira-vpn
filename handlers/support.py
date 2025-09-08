# handlers/support.py
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings

router = Router()

def rtl(s: str) -> str: return "\u200F" + s

def support_kb():
    username = settings.SUPPORT_USERNAME.lstrip("@")
    url = f"https://t.me/{username}"
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("گفتگو در تلگرام"), url=url)
    kb.adjust(1)
    return kb.as_markup()

@router.message(F.text == "🛟 پشتیبانی")
async def support_handler(m: types.Message):
    await m.answer(
        rtl("🛟 پشتیبانی: با زدن دکمهٔ زیر مستقیم به پشتیبان پیام بده."),
        reply_markup=support_kb()
    )
