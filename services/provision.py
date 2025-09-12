# services/provision.py
from datetime import datetime, timedelta

from aiogram import Bot
from bson import ObjectId

from db.mongo import subscriptions_col, plans_col, orders_col, users_col
from services.xray_service import add_client
import asyncio

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

    # ایمیل/برچسب: یکتا بر اساس کاربر و سفارش
    email = f"{str(user['_id'])[-6:]}-{str(order['_id'])[-6:]}@bot"

    # ساخت کاربر روی Xray
    uuid_str, vless_link = add_client(email)

    now = datetime.utcnow()
    sub_doc = {
        "user_id": user["_id"],
        "order_id": order["_id"],
        "source_plan": plan["code"],
        "quota_mb": int(plan["gb"]) * 1024,  # MB
        "used_mb": 0,
        "devices": int(plan.get("devices", 1)),
        "start_at": now,
        "end_at": now + timedelta(days=int(plan["days"])),
        "status": "active",
        "config_ref": vless_link,  # همینجا لینک را ذخیره می‌کنیم
        "xray": {"email": email, "uuid": uuid_str},
    }
    uuid_str, vless_link = await asyncio.to_thread(add_client, email)
    await subscriptions_col.insert_one(sub_doc)

    # پیام به کاربر
    tg_id = user.get("tg_id")
    if tg_id is not None:
        txt = (
            "\u200F"
            "🎉 اشتراک شما فعال شد.\n\n"
            f"• پلن: {plan['title']}\n"
            f"• حجم: {plan['gb']} گیگ / مدت: {plan['days']} روز / دستگاه: {plan.get('devices', 1)}\n"
            f"• لینک اتصال:\n<code>{vless_link}</code>\n\n"
            "راهنما: کانفیگ را در اپ کلاینت وارد کرده و وصل شوید. اگر سوالی بود «🛟 پشتیبانی» در منو."
        )
        try:
            await bot.send_message(int(tg_id), txt, disable_web_page_preview=True)
        except Exception:
            pass

    return True
