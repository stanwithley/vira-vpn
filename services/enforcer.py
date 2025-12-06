# services/enforcer.py
import asyncio
import logging
from datetime import datetime, timezone
from db.mongo import subscriptions_col
# تغییر مهم: استفاده از کلاس جدید
from services.xray_service import XrayService

logger = logging.getLogger(__name__)

# ساخت نمونه از سرویس پنل
xray = XrayService()


async def expire_loop(interval_sec: int = 600):  # چک کردن هر ۱۰ دقیقه کافیه
    logger.info("⏳ Expiration enforcer started.")
    while True:
        try:
            now = datetime.now(timezone.utc)
            # پیدا کردن اشتراک‌های فعال که زمانشان تمام شده
            cursor = subscriptions_col.find({
                "status": "active",
                "end_at": {"$lte": now}
            })

            count = 0
            async for s in cursor:
                # استخراج ایمیل‌ها برای حذف از پنل
                emails_to_remove = []

                # سازگاری با مدل جدید (لیست ایمیل‌ها در xray)
                xray_accounts = s.get("xray")
                if isinstance(xray_accounts, list):
                    for acc in xray_accounts:
                        if isinstance(acc, dict) and acc.get("email"):
                            emails_to_remove.append(acc.get("email"))

                # سازگاری با مدل قدیمی (اگر احتمالا مانده باشد)
                elif isinstance(xray_accounts, dict) and xray_accounts.get("email"):
                    emails_to_remove.append(xray_accounts["email"])

                # حذف تک‌تک یوزرها از پنل
                for email in emails_to_remove:
                    try:
                        # صدا زدن متد جدید کلاس (با await)
                        await xray.remove_client(email)
                    except Exception as e:
                        logger.error(f"Failed to remove xray client {email}: {e}")

                # آپدیت وضعیت در دیتابیس
                await subscriptions_col.update_one(
                    {"_id": s["_id"]},
                    {"$set": {"status": "expired"}}
                )

                # لاگ کردن برای اطلاع ادمین
                user_id = s.get("user_id")
                logger.info(f"Subscription {s['_id']} for user {user_id} expired and removed.")
                count += 1

            if count > 0:
                logger.info(f"🧹 Cleaned up {count} expired subscriptions.")

        except Exception as e:
            logger.error(f"❌ Error in expire_loop: {e}")
            # اگر خطای اتصال دیتابیس باشه، نباید لوپ بشکنه، فقط صبر میکنه

        await asyncio.sleep(interval_sec)