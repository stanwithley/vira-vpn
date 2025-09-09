# handlers/admin_manage.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

from config import settings
from db.mongo_crud import add_admin, remove_admin, list_admins, is_admin_db

router = Router()

# --- Helpers ---
def is_root_admin(uid: int) -> bool:
    """فقط اولین عدد در settings.admin_ids به‌عنوان مالک (Root) شناخته می‌شود."""
    return len(getattr(settings, "admin_ids", [])) > 0 and uid == settings.admin_ids[0]

def is_admin(uid: int) -> bool:
    """Root Adminهای config یا سایر ادمین‌های ذخیره‌شده در DB"""
    if uid in getattr(settings, "admin_ids", []):
        return True
    return is_admin_db(uid)

# --- /add_admin <user_id> ---
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

    # جلوگیری از دوباره‌کاری: اگر خودش Root باشد، نیازی به DB نیست
    if uid in getattr(settings, "admin_ids", []):
        return await m.answer("ℹ️ این کاربر در Root Adminهای config است و دسترسی دارد.")

    ok = add_admin(uid=uid, username=None, added_by=m.from_user.id)
    if ok:
        await m.answer(f"✅ ادمین با ID <code>{uid}</code> اضافه شد.", parse_mode="HTML")
    else:
        await m.answer("ℹ️ این کاربر قبلاً ادمین بوده.")

# --- /remove_admin <user_id> ---
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

    # جلوگیری از حذف Root Admin اصلی
    if uid in getattr(settings, "admin_ids", []) and uid == settings.admin_ids[0]:
        return await m.answer("❌ نمی‌توان Root Admin اصلی را حذف کرد.")

    ok = remove_admin(uid)
    if ok:
        await m.answer(f"🗑 ادمین با ID <code>{uid}</code> حذف شد.", parse_mode="HTML")
    else:
        await m.answer("ℹ️ چنین ادمینی در DB یافت نشد یا از Rootهاست.")

# --- /admins ---
@router.message(Command("admins"))
async def admins_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ دسترسی ندارید.")

    rows = list_admins()
    if not rows:
        return await m.answer("لیست ادمین‌ها خالی است.")

    # نمایش مرتب
    by_tag = {"root": [], "admin": []}
    for r in rows:
        tag = "root" if r.get("is_root") else "admin"
        uname = f" (@{r['username']})" if r.get("username") else ""
        by_tag[tag].append(f"{'👑 Root' if tag=='root' else '🛡 Admin'} — <code>{r['uid']}</code>{uname}")

    lines = []
    if by_tag["root"]:
        lines.append("👑 <b>Root Admins</b>")
        lines.extend(by_tag["root"])
        lines.append("")
    if by_tag["admin"]:
        lines.append("🛡 <b>Admins</b>")
        lines.extend(by_tag["admin"])

    await m.answer("\n".join(lines), parse_mode="HTML")
