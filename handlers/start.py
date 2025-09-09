# handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from db.mongo_crud import get_or_create_user

router = Router()


@router.message(CommandStart())
async def start_cmd(m: Message):
    # اگر deep-link داشت، اینجا به‌درد می‌خوره
    args = m.text.split(maxsplit=1)[1] if (m.text and " " in m.text) else None

    # ساخت/آپدیت کاربر
    await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name
    )

    # پاسخ خوش‌آمد
    if args:
        await m.answer(f"سلام 👋\nکدت رو گرفتم: <code>{args}</code>", parse_mode="HTML")
        # اینجا می‌تونی براساس args کاری کنی (ارجاع، کمپین، پلن تریال، ...)
    else:
        await m.answer("سلام 👋\nبه بات خوش اومدی!")
