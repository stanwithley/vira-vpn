# services/provision.py
from datetime import datetime, timedelta
from aiogram import Bot
from bson import ObjectId

from db.mongo import subscriptions_col, plans_col, orders_col, users_col
from services.xray_service import add_client

async def provision_paid_order(order_id: ObjectId, bot: Bot) -> bool:
    order = await orders_col.find_one({"_id": ObjectId(str(order_id))})
    if not order or order.get("status") != "paid":
        return False

    user = await users_col.find_one({"_id": order["user_id"]})
    if not user:
        return False

    plan = await plans_col.find_one({"code": order["plan_code"], "active": True})
    if not plan:
        return False

    # تعداد دستگاه
    dev_count = int(plan.get("devices", 1))

    # برای هر دستگاه یک ایمیل/UUID/لینک جدا
    links = []
    xray_accounts = []
    for i in range(dev_count):
        email = f"{str(user['_id'])[-6:]}-{str(order['_id'])[-6:]}-{i+1}@bot"
        uuid_str, vless_link = add_client(email)
        links.append(vless_link)
        xray_accounts.append({"email": email, "uuid": uuid_str})

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
        "config_ref": links,      # ⬅️ لیست لینک‌ها
        "xray": xray_accounts,    # ⬅️ لیست ایمیل/UUID
    }
    await subscriptions_col.insert_one(sub_doc)

    # پیام به کاربر (همه لینک‌ها)
    tg_id = user.get("tg_id")
    if tg_id is not None:
        lines = [
            "\u200F",
            "🎉 اشتراک شما فعال شد.",
            "",
            f"• پلن: {plan['title']}",
            f"• حجم: {plan['gb']} گیگ / مدت: {plan['days']} روز / دستگاه: {dev_count}",
            "• لینک‌های اتصال:"
        ]
        for idx, link in enumerate(links, 1):
            lines.append(f"{idx}) <code>{link}</code>")
        lines.append("\nراهنما: هر دستگاه از یکی از لینک‌ها استفاده کند.")
        txt = "\n".join(lines)
        try:
            await bot.send_message(int(tg_id), txt, disable_web_page_preview=True)
        except Exception:
            pass

    return True
