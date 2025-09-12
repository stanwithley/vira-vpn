# handlers/mysubs.py (جایگزین استاب فعلی)
from aiogram import Router, types, F
from db.mongo_crud import get_or_create_user
from db.mongo import subscriptions_col
from utils.locale import rtl, fa_num, fmt_dt

router = Router()

@router.message(F.text == "📦 اشتراک‌های من")
async def my_subs(m: types.Message):
    user = await get_or_create_user(m.from_user.id, m.from_user.username, m.from_user.first_name)
    subs = [s async for s in subscriptions_col.find({"user_id": user["_id"]}).sort("start_at", -1).limit(5)]
    if not subs:
        return await m.answer(rtl("فعلاً اشتراکی نداری. بعد از خرید، اینجا لیست می‌کنیم 📋"))

    lines = []
    for s in subs:
        left_mb = max(0, int(s.get("quota_mb", 0)) - int(s.get("used_mb", 0)))
        link = s.get("config_ref")
        lines.append(
            rtl(
                f"• پلن: {s.get('source_plan')}\n"
                f"  حجم: {fa_num(str(int(s.get('quota_mb',0))))} مگ | مصرف: {fa_num(str(int(s.get('used_mb',0))))} مگ | باقی: {fa_num(str(left_mb))} مگ\n"
                f"  از: {fmt_dt(s['start_at'])} تا: {fmt_dt(s['end_at'])}\n"
                f"  وضعیت: {s.get('status')}\n"
                + (f"  لینک:\n<code>{link}</code>\n" if link else "")
            )
        )
    await m.answer("\n\n".join(lines), disable_web_page_preview=True)
