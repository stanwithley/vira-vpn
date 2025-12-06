# handlers/mysubs.py
from aiogram import Router, types, F
from db.mongo_crud import get_or_create_user
from db.mongo import subscriptions_col
from utils.locale import rtl, fa_num, fmt_dt
from config import settings  # <--- برای ساخت لینک نیاز داریم

router = Router()


def _generate_vless_link(uuid_str: str, name: str) -> str:
    """ساخت لینک VLESS بر اساس تنظیمات کانفیگ"""
    # این فرمت استاندارد VLESS WS است
    # اگر پورت یا آدرس عوض شد، لینک مشتری هم خودکار درست میشه
    return (
        f"vless://{uuid_str}@{settings.XRAY_DOMAIN}:{settings.XRAY_PORT}"
        f"?type=ws&security={settings.XRAY_SECURITY}&path={settings.XRAY_WS_PATH}"
        f"&fp=chrome&alpn=http/1.1#{name}"
    )


def _generate_sub_link(uuid_str: str) -> str:
    """ساخت لینک اشتراک (Subscription)"""
    # لینک اشتراک پنل سنایی
    # نکته: این لینک خیلی بهتر از VLESS خالیه چون آپدیت میشه
    base = settings.PANEL_URL.rstrip("/")
    return f"{base}/sub/{uuid_str}"


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
        used_mb = int(s.get("used_mb") or 0)
        left_mb = max(0, quota_mb - used_mb)
        devices = int(s.get("devices") or 1)
        status = s.get("status") or "unknown"

        # اطلاعات جدید
        uuid_str = s.get("uuid")
        email_name = s.get("email") or "ViraVPN"

        # تیتر هر سطر
        title = s.get("source_plan") or "—"

        # ساخت متن نمایش
        lines = [
            rtl(f"🏷 پلن: {title}"),
            rtl(f"📊 حجم: {fa_num(quota_mb)} مگ | مصرف: {fa_num(used_mb)} مگ"),
            rtl(f"📱 دستگاه: {fa_num(devices)} | وضعیت: {status}"),
            rtl(f"📅 انقضا: {fmt_dt(s['end_at'])}"),
        ]

        # --- بخش هوشمند لینک ---
        links = []

        # 1. اگر لینک قدیمی دستی هست، اونو نشون بده
        if s.get("config_ref"):
            raw = s.get("config_ref")
            if isinstance(raw, list):
                links.extend(raw)
            else:
                links.append(str(raw))

        # 2. اگر UUID داریم (سیستم جدید)، لینک تولید کن
        elif uuid_str:
            # لینک اشتراک (خیلی مهمه)
            sub_link = _generate_sub_link(uuid_str)
            lines.append(rtl("\n🔄 <b>لینک اشتراک (هوشمند):</b>"))
            lines.append(f"<code>{sub_link}</code>")

            # لینک مستقیم VLESS (برای کسانی که ساب نمیخوان)
            vless_link = _generate_vless_link(uuid_str, email_name)
            links.append(vless_link)

        if links:
            lines.append(rtl("\n🔗 <b>لینک اتصال مستقیم:</b>"))
            for i, link in enumerate(links, 1):
                # اگر فقط یه لینک بود شماره نزن
                prefix = f"{fa_num(i)}) " if len(links) > 1 else ""
                lines.append(f"{prefix}<code>{link}</code>")

        blocks.append("\n".join(lines))
        blocks.append("〰️〰️〰️〰️〰️")  # جداکننده

    await m.answer("\n".join(blocks), disable_web_page_preview=True, parse_mode="HTML")