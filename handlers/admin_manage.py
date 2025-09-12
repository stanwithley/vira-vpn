# handlers/admin_manage.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

from config import settings
from db.mongo_crud import add_admin, remove_admin, list_admins, is_admin_db

router = Router()

ADMIN_IDS = getattr(settings, "ADMIN_CHAT_IDS", [])

def is_root_admin(uid: int) -> bool:
    return len(ADMIN_IDS) > 0 and uid == ADMIN_IDS[0]

async def is_admin(uid: int) -> bool:
    # باید await بشه
    return (uid in set(ADMIN_IDS)) or (await is_admin_db(uid))

@router.message(Command("add_admin"))
async def add_admin_cmd(m: Message, command: CommandObject):
    if not is_root_admin(m.from_user.id):
        return await m.answer("⛔ فقط مالک بات می‌تواند ادمین اضافه کند.")

    if not command.args:
        return await m.answer("فرمت: /add_admin <user_id>\nمثال: /add_admin 123456789")

    try:
        uid = int(command.args.strip())
    except ValueError:
        return await m.answer("❌ user_id باید عدد باشد.")

    # این چکِ اشتباه رو حذف کن یا به ADMIN_IDS اصلاح کن؛ admin_ids در Settings نداری
    if uid in ADMIN_IDS:
        return await m.answer("ℹ️ این کاربر در Root Adminهای config است و دسترسی دارد.")

    ok = await add_admin(uid=uid, username=None, added_by=m.from_user.id)  # ← await
    if ok:
        await m.answer(f"✅ ادمین با ID <code>{uid}</code> اضافه شد.", parse_mode="HTML")
    else:
        await m.answer("ℹ️ این کاربر قبلاً ادمین بوده.")

@router.message(Command("remove_admin"))
async def remove_admin_cmd(m: Message, command: CommandObject):
    if not is_root_admin(m.from_user.id):
        return await m.answer("⛔ فقط مالک بات می‌تواند ادمین حذف کند.")

    if not command.args:
        return await m.answer("فرمت: /remove_admin <user_id>\nمثال: /remove_admin 123456789")

    try:
        uid = int(command.args.strip())
    except ValueError:
        return await m.answer("❌ user_id باید عدد باشد.")

    if uid in ADMIN_IDS and uid == ADMIN_IDS[0]:
        return await m.answer("❌ نمی‌توان Root Admin اصلی را حذف کرد.")

    ok = await remove_admin(uid)  # ← await
    if ok:
        await m.answer(f"🗑 ادمین با ID <code>{uid}</code> حذف شد.", parse_mode="HTML")
    else:
        await m.answer("ℹ️ چنین ادمینی در DB یافت نشد یا از Rootهاست.")

@router.message(Command("admins"))
async def admins_cmd(m: Message):
    if not (await is_admin(m.from_user.id)):   # ← await
        return await m.answer("⛔ دسترسی ندارید.")

    rows = await list_admins()  # ← await
    if not rows:
        return await m.answer("لیست ادمین‌ها خالی است.")

    lines = []
    lines.append("👑 <b>Root Admins</b>")
    for rid in ADMIN_IDS[:1]:
        lines.append(f"👑 Root — <code>{rid}</code>")

    norm = [r for r in rows if not r.get("is_root")]
    if norm:
        lines.append("")
        lines.append("🛡 <b>Admins</b>")
        for r in norm:
            uname = f" (@{r['username']})" if r.get("username") else ""
            lines.append(f"🛡 Admin — <code>{r['uid']}</code>{uname}")

    await m.answer("\n".join(lines), parse_mode="HTML")
