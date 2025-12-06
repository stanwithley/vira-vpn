# services/provision.py
from datetime import datetime, timedelta
from aiogram import Bot
from bson import ObjectId

from db.mongo import subscriptions_col, plans_col, orders_col, users_col
# تغییر مهم: استفاده از سرویس جدید
from services.xray_service import XrayService
from config import settings

# ساخت نمونه از کلاس ارتباط با پنل
xray = XrayService()


async def provision_paid_order(order_id: ObjectId, bot: Bot) -> bool:
    # 1. دریافت اطلاعات سفارش
    order = await orders_col.find_one({"_id": ObjectId(str(order_id))})
    if not order or order.get("status") != "paid":
        return False

    user = await users_col.find_one({"_id": order["user_id"]})
    if not user:
        return False

    plan = await plans_col.find_one({"code": order["plan_code"], "active": True})
    if not plan:
        return False

    # 2. آماده‌سازی اطلاعات برای پنل
    # نام‌گذاری ایمیل: u[آیدی‌تلگرام]-[تکه‌ای‌از‌سفارش]
    # مثال: u12345678-a1b2
    email = f"u{user.get('tg_id')}-{str(order['_id'])[-4:]}"

    dev_count = int(plan.get("devices", 1))
    total_gb = int(plan.get("gb", 0))
    days = int(plan.get("days", 30))

    # 3. ارسال درخواست به پنل (API)
    # به جای حلقه زدن، یک اکانت با لیمیت آی‌پی می‌سازیم
    result = await xray.add_client(
        email=email,
        limit_ip=dev_count,
        total_gb=total_gb,
        expire_days=days
    )

    if not result:
        # اگر خطا داد (مثلاً پنل پایین بود)
        try:
            await bot.send_message(settings.ADMIN_CHAT_IDS[0], f"⚠️ خطا در ساخت سرویس برای سفارش {order_id}")
        except:
            pass
        return False

    # استخراج اطلاعات ساخته شده
    uuid_str = result["uuid"]
    vless_link = result["link"]

    # ساخت لینک اشتراک (هوشمند)
    # مثال: http://ip:port/sub/UUID
    sub_link = f"{settings.PANEL_URL.rstrip('/')}/sub/{uuid_str}"

    # 4. ذخیره در دیتابیس (با فرمت جدید)
    now = datetime.utcnow()
    sub_doc = {
        "user_id": user["_id"],
        "order_id": order["_id"],
        "source_plan": plan["code"],
        "quota_mb": total_gb * 1024,
        "used_mb": 0,
        "devices": dev_count,
        "start_at": now,
        "end_at": now + timedelta(days=days),
        "status": "active",

        # فیلدهای حیاتی جدید
        "uuid": uuid_str,
        "email": email,
        "config_ref": [vless_link],  # لینک مستقیم به عنوان بکاپ
        "xray": [{"email": email, "uuid": uuid_str}]  # جهت سازگاری
    }
    await subscriptions_col.insert_one(sub_doc)

    # 5. ارسال پیام تبریک به کاربر
    tg_id = user.get("tg_id")
    if tg_id is not None:
        lines = [
            "\u200F",  # راست‌چین ساز
            "🎉 <b>اشتراک شما با موفقیت فعال شد!</b>",
            "",
            f"🏷 پلن: {plan['title']}",
            f"📊 حجم: {plan['gb']} گیگ",
            f"⏳ مدت: {plan['days']} روز",
            f"📱 تعداد کاربر مجاز: {dev_count} نفر",
            "",
            "⬇️ <b>لینک اشتراک (پیشنهادی):</b>",
            f"<code>{sub_link}</code>",
            "",
            "ℹ️ این لینک را در نرم‌افزار (v2rayNG / V2Box / Streisand) وارد کنید و Update بزنید.",
            "",
            "🔗 <b>لینک مستقیم (کمکی):</b>",
            f"<code>{vless_link}</code>"
        ]

        txt = "\n".join(lines)
        try:
            await bot.send_message(
                int(tg_id),
                txt,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            pass

    return True