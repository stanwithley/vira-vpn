# services/provision.py
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from bson import ObjectId

from db.mongo import subscriptions_col, plans_col, orders_col, users_col
from services.xray_service import XrayService
from config import settings

# تنظیم لاگر
logger = logging.getLogger(__name__)

xray = XrayService()


async def provision_paid_order(order_id: ObjectId | str, bot: Bot) -> bool:
    logger.info(f"🚀 STARTING PROVISION for Order: {order_id}")

    try:
        # 1. دریافت اطلاعات سفارش
        if isinstance(order_id, str):
            order_id = ObjectId(order_id)

        order = await orders_col.find_one({"_id": order_id})
        if not order:
            logger.error(f"❌ Order {order_id} not found in DB!")
            return False

        if order.get("status") != "paid":
            logger.warning(
                f"⚠️ Order {order_id} status is '{order.get('status')}', expected 'paid'. Continuing anyway...")

        # 2. پیدا کردن کاربر و پلن
        user = await users_col.find_one({"_id": order["user_id"]})
        plan = await plans_col.find_one(
            {"code": order["plan_code"]})  # active=True رو برداشتیم شاید پلن غیرفعال شده باشه

        if not user or not plan:
            logger.error("❌ User or Plan not found for this order.")
            return False

        logger.info(f"👤 User: {user.get('tg_id')} | 📦 Plan: {plan.get('code')}")

        # 3. آماده‌سازی داده‌ها
        email = f"u{user.get('tg_id')}-{str(order['_id'])[-4:]}"
        dev_count = int(plan.get("devices", 1))
        total_gb = int(plan.get("gb", 0))
        days = int(plan.get("days", 30))

        logger.info(f"⚙️ Requesting Xray: Email={email}, GB={total_gb}, Days={days}, Limit={dev_count}")

        # 4. درخواست به پنل
        try:
            result = await xray.add_client(
                email=email,
                limit_ip=dev_count,
                total_gb=total_gb,
                expire_days=days
            )
        except Exception as e:
            logger.exception(f"❌ CRITICAL ERROR inside xray.add_client: {e}")
            return False

        if not result:
            logger.error("❌ xray.add_client returned None (Panel Error).")
            # خبر دادن به ادمین
            try:
                await bot.send_message(settings.ADMIN_CHAT_IDS[0],
                                       f"⚠️ خطا در ساخت کانفیگ برای سفارش {order_id}\nلاگ را چک کنید.")
            except:
                pass
            return False

        logger.info("✅ Client created in Panel successfully.")

        uuid_str = result["uuid"]
        vless_link = result["link"]
        sub_link = f"{settings.PANEL_URL.rstrip('/')}/sub/{uuid_str}"

        # 5. ذخیره در دیتابیس
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
            "uuid": uuid_str,
            "email": email,
            "config_ref": [vless_link],
            "xray": [{"email": email, "uuid": uuid_str}]
        }
        await subscriptions_col.insert_one(sub_doc)
        logger.info("💾 Subscription saved to MongoDB.")

        # 6. ارسال پیام به کاربر
        tg_id = user.get("tg_id")
        if tg_id:
            txt = (
                f"🎉 <b>اشتراک شما فعال شد!</b>\n\n"
                f"📊 حجم: {plan['gb']} گیگ\n"
                f"⏳ مدت: {plan['days']} روز\n\n"
                f"⬇️ <b>لینک اشتراک (بزن روش کپی شه):</b>\n"
                f"<code>{sub_link}</code>\n\n"
                f"🔗 <b>لینک کمکی:</b>\n"
                f"<code>{vless_link}</code>"
            )
            try:
                await bot.send_message(tg_id, txt, parse_mode="HTML")
                logger.info(f"📩 Message sent to user {tg_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send message to user: {e}")

        return True

    except Exception as e:
        logger.exception(f"❌ UNEXPECTED ERROR in provision_paid_order: {e}")
        return False