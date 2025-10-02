# handlers/admin_manage.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

from config import settings
from db.mongo_crud import add_admin, remove_admin, list_admins, is_admin_db

router = Router()

# List[int]؛ از settings خوانده می‌شود (در بخش 2 تنظیمش می‌کنیم)
ADMIN_IDS: list[int] = list(getattr(settings, "ADMIN_CHAT_IDS", []))

def is_root_admin(uid: int) -> bool:
    """RootAdmin = اولین آیتمِ ADMIN_CHAT_IDS در .env"""
    return bool(ADMIN_IDS) and int(uid) == int(ADMIN_IDS[0])

async def is_admin(uid: int) -> bool:
    """ادمین = Root یا داخل جدول admins."""
    return is_root_admin(uid) or (await is_admin_db(uid))

def _extract_uid_from_args_or_reply(m: Message, command: CommandObject) -> int | None:
    # اولویت با آرگومان
    if command and command.args:
        s = command.args.strip()
        if s.isdigit():
            return int(s)
    # اگر ریپلای باشد، از ارسال‌کنندهٔ پیامِ ریپلای استفاده کن
    if m.reply_to_message and m.reply_to_message.from_user:
        return int(m.reply_to_message.from_user.id)
    return None

@router.message(Command("admin"))
async def admin_home(m: Message):
    if not (await is_admin(m.from_user.id)):
        return await m.answer("\u200F⛔ این بخش مخصوص ادمین‌هاست.")
    await m.answer(
        "\u200Fپَنل ادمین:\n"
        "• /admins — فهرست ادمین‌ها\n"
        "• /add_admin <uid> — افزودن ادمین (فقط Root)\n"
        "• /remove_admin <uid> — حذف ادمین (فقط Root)\n"
        "• /whoami — اطلاعات شما\n"
        "• /ping — تست"
    )

@router.message(Command("whoami"))
async def whoami(m: Message):
    role = "Root" if is_root_admin(m.from_user.id) else ("Admin" if (await is_admin_db(m.from_user.id)) else "User")
    await m.answer(
        "\u200F"
        f"uid: <code>{m.from_user.id}</code>\n"
        f"username: @{m.from_user.username or '-'}\n"
        f"role: {role}",
        parse_mode="HTML"
    )

@router.message(Command("ping"))
async def ping(m: Message):
    await m.answer("\u200Fpong ✅")

@router.message(Command("admins"))
async def admins_cmd(m: Message):
    if not (await is_admin(m.from_user.id)):
        return await m.answer("\u200F⛔ دسترسی ندارید.")
    rows = await list_admins()
    lines = ["\u200F👑 <b>Root Admins</b>"]
    if ADMIN_IDS:
        lines.append(f"👑 Root — <code>{ADMIN_IDS[0]}</code>")
    else:
        lines.append("— (تعریف نشده)")
    norm = [r for r in rows]
    if norm:
        lines.append("")
        lines.append("🛡 <b>Admins</b>")
        for r in norm:
            uname = f" (@{r['username']})" if r.get("username") else ""
            lines.append(f"🛡 Admin — <code>{r['uid']}</code>{uname}")
    await m.answer("\n".join(lines), parse_mode="HTML")

@router.message(Command("add_admin"))
async def add_admin_cmd(m: Message, command: CommandObject):
    if not is_root_admin(m.from_user.id):
        return await m.answer("\u200F⛔ فقط Root Admin می‌تواند ادمین اضافه کند.")
    uid = _extract_uid_from_args_or_reply(m, command)
    if uid is None:
        return await m.answer("فرمت: /add_admin <user_id>\nیا روی پیام کاربر ریپلای و دستور را بفرست.")
    if is_root_admin(uid):
        return await m.answer("ℹ️ این کاربر Root است.")
    ok = await add_admin(uid=uid, username=m.from_user.username, added_by=m.from_user.id)
    await m.answer(
        f"✅ ادمین با ID <code>{uid}</code> اضافه شد." if ok else "ℹ️ این کاربر قبلاً ادمین بوده.",
        parse_mode="HTML"
    )

@router.message(Command("remove_admin"))
async def remove_admin_cmd(m: Message, command: CommandObject):
    if not is_root_admin(m.from_user.id):
        return await m.answer("\u200F⛔ فقط Root Admin می‌تواند ادمین حذف کند.")
    uid = _extract_uid_from_args_or_reply(m, command)
    if uid is None:
        return await m.answer("فرمت: /remove_admin <user_id>\nیا روی پیام کاربر ریپلای و دستور را بفرست.")
    if is_root_admin(uid):
        return await m.answer("❌ نمی‌توان Root Admin را حذف کرد.")
    ok = await remove_admin(uid)
    await m.answer(
        f"🗑 ادمین با ID <code>{uid}</code> حذف شد." if ok else "ℹ️ چنین ادمینی در DB نیست.",
        parse_mode="HTML"
    )
