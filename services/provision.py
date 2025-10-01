# services/provision.py
from datetime import datetime, timedelta
from aiogram import Bot
from bson import ObjectId

from db.mongo import subscriptions_col, plans_col, orders_col, users_col
from services.xray_service import add_client
from services.links import vless_ws_link  # سازنده لینک یکدست و تمیز
from config import settings               # تا XRAY_* را از .env بخوانیم


async def provision_paid_order(order_id: ObjectId, bot: Bot) -> bool:
    # --- اعتبارسنجی سفارش/کاربر/پلن ---
    order = await orders_col.find_one({"_id": ObjectId(str(order_id))})
    if not order or order.get("status") != "paid":
        return False

    user = await users_col.find_one({"_id": order["user_id"]})
    if not user:
        return False

    plan = await plans_col.find_one({"code": order["plan_code"], "active": True})
    if not plan:
        return False

    # --- تعداد دستگاه ---
    dev_count = int(plan.get("devices", 1))

    # --- برای هر دستگاه: add_client (گرفتن UUID) + ساخت لینک با env جاری ---
    links: list[str] = []
    xray_accounts: list[dict] = []

    # مقادیر اتصال از .env / settings
    host     = getattr(settings, "XRAY_HOST", getattr(settings, "XRAY_DOMAIN", "127.0.0.1"))
    port     = int(getattr(settings, "XRAY_PORT", 8081))
    ws_path  = getattr(settings, "XRAY_WS_PATH", "/ws8081")
    security = getattr(settings, "XRAY_SECURITY", "none")

    for i in range(dev_count):
        # ایمیل یکتا برای آمار و مدیریت
        email = f"{str(user['_id'])[-6:]}-{str(order['_id'])[-6:]}-{i+1}@bot"

        # add_client: یوزر را به Xray اضافه می‌کند و UUID می‌دهد
        uuid_str, _unused_link = add_client(email)

        # لینک استاندارد و تمیز با سازنده‌ی مشترک
        tag = f"{(user.get('username') or str(user.get('tg_id') or 'user')).replace('@','')}-{i+1}"
        link = vless_ws_link(uuid_str, host, port, ws_path, security, tag)

        links.append(link)
        xray_accounts.append({"email": email, "uuid": uuid_str})

    # --- ثبت اشتراک در DB ---
    now = datetime.utcnow()
    sub_doc = {
        "user_id": user["_id"],
        "order_id": order["_id"],
        "source_plan": plan["code"],
        "quota_mb": int(plan["gb"]) * 1024,  # MB
        "used_mb": 0,
        "devices": dev_count,
        "start_at": now,
        "end_at": now + timedelta(days=int(plan["days"])),
        "status": "active",
        "config_ref": links,      # لیست لینک‌ها
        "xray": xray_accounts,    # ایمیل/UUID برای مدیریت و آمار
    }
    await subscriptions_col.insert_one(sub_doc)

    # --- ارسال لینک‌ها به کاربر ---
    tg_id = user.get("tg_id")
    if tg_id is not None:
        # پیام HTML: چون <code> داریم، parse_mode="HTML" لازم است
        # هر لینک در خط جدا + بدون هیچ متن وسط لینک
        lines = [
            "\u200F",
            "🎉 اشتراک شما فعال شد.",
            "",
            f"• پلن: {plan['title']}",
            f"• حجم: {plan['gb']} گیگ / مدت: {plan['days']} روز / دستگاه: {dev_count}",
            "• لینک‌های اتصال:",
        ]
        for idx, link in enumerate(links, 1):
            lines.append(f"{idx}) <code>{link}</code>")
        lines.append("")
        lines.append("راهنما: هر دستگاه از یکی از لینک‌ها استفاده کند.")

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
