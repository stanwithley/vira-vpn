# db/mongo.py
import motor.motor_asyncio

from config import settings

client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

users_col          = db["users"]
plans_col          = db["plans"]
orders_col         = db["orders"]
subscriptions_col  = db["subscriptions"]
admins_col         = db["admins"]
payments_col       = db["payments"]


async def ensure_indexes() -> None:
    # === users ===
    # هر کاربر تلگرام یکبار
    await users_col.create_index("tg_id", unique=True)

    # === plans ===
    await plans_col.create_index("code", unique=True)
    await plans_col.create_index([("active", 1)])

    # === orders ===
    # جست‌وجوی پرتکرار: سفارش‌های کاربر بر اساس وضعیت و زمان
    await orders_col.create_index([("user_id", 1), ("status", 1), ("created_at", -1)])
    await orders_col.create_index("created_at")

    # === subscriptions ===
    # نمایش و مانیتورینگ: اشتراک‌های کاربر/وضعیت/نزدیک‌ترین پایان
    await subscriptions_col.create_index([("user_id", 1), ("status", 1), ("end_at", -1)])
    # برای کرون/لوپ‌های پایان اعتبار یا سهمیه
    await subscriptions_col.create_index("end_at")

    # === payments ===
    # گرفتن آخرین پرداخت‌های یک سفارش + فیلتر وضعیت
    await payments_col.create_index([("order_id", 1), ("status", 1), ("created_at", -1)])
    await payments_col.create_index("status")

    # === admins ===
    await admins_col.create_index("uid", unique=True)
