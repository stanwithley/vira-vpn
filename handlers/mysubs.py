# handlers/mysubs.py
from aiogram import Router, types, F
from db.mongo_crud import get_or_create_user
from db.mongo import subscriptions_col
from utils.locale import rtl, fa_num, fmt_dt

router = Router()

def _to_links_list(cfg_ref) -> list[str]:
    if not cfg_ref:
        return []
    if isinstance(cfg_ref, str):
        return [cfg_ref]
    if isinstance(cfg_ref, list):
        # فقط رشته‌ها را نگه داریم
        return [s for s in cfg_ref if isinstance(s, str) and s.strip()]
    return []

@router.message(F.text == "📦 اشتراک‌های من")
async def my_subs(m: types.Message):
    user = await get_or_create_user(m.from_user.id, m.from_user.username, m.from_user.first_name)

    # آخرین ۵ اشتراک کاربر
    cursor = subscriptions_col.find({"user_id": user["_id"]}).sort("start_at", -1).limit(5)
    subs = [s async for s in cursor]

    if not subs:
        return await m.answer(rtl("فعلاً اشتراکی نداری. بعد از خرید، اینجا لیست می‌کنیم 📋"))

    blocks = []
    for s in subs:
        quota_mb = int(s.get("quota_mb") or 0)
        used_mb  = int(s.get("used_mb")  or 0)
        left_mb  = max(0, quota_mb - used_mb)
        devices  = int(s.get("devices")  or 1)
        status   = s.get("status") or "unknown"

        # لینک‌ها را به لیست نرمال کنیم
        links = _to_links_list(s.get("config_ref"))

        # تیتر هر سطر
        title = s.get("source_plan") or "—"
        # ساخت متن
        lines = [
            rtl(f"• پلن: {title}"),
            rtl(
                f"  حجم: {fa_num(quota_mb)} مگ | مصرف: {fa_num(used_mb)} مگ | باقی: {fa_num(left_mb)} مگ"
            ),
            rtl(
                f"  دستگاه: {fa_num(devices)} | وضعیت: {status}"
            ),
            rtl(
                f"  از: {fmt_dt(s['start_at'])} تا: {fmt_dt(s['end_at'])}"
            ),
        ]

        if links:
            lines.append(rtl("  لینک‌ها:"))
            for i, link in enumerate(links, 1):
                lines.append(f"{fa_num(i)}) <code>{link}</code>")

        blocks.append("\n".join(lines))

    # چون از <code> استفاده می‌کنیم، parse_mode باید HTML باشد
    await m.answer("\n\n".join(blocks), disable_web_page_preview=True, parse_mode="HTML")
