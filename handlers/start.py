# handlers/start.py
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from db.mongo_crud import get_or_create_user
from keyboards.main_menu import main_menu

router = Router()

def _extract_start_arg(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else None

@router.message(CommandStart())
async def start_cmd(m: Message):
    # Deep-link payload (e.g. /start promo123)
    arg = _extract_start_arg(m.text)

    # Create/update user in DB (idempotent)
    await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username or None,
        first_name=m.from_user.first_name or None,
    )

    # Welcome text
    lines = ["سلام 👋", "به بات خوش اومدی!"]
    if arg:
        lines.append(f"کدت رو گرفتم: <code>{arg}</code>")
    text = "\n".join(lines)

    await m.answer(text, parse_mode="HTML", reply_markup=main_menu())
