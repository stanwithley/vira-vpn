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
    await users_col.create_index("tg_id", unique=True)

    # === plans ===
    await plans_col.create_index("code", unique=True)
    await plans_col.create_index([("active", 1)])

    # === orders ===
    await orders_col.create_index([("user_id", 1), ("status", 1), ("created_at", -1)])
    await orders_col.create_index("created_at")

    # === subscriptions ===
    await subscriptions_col.create_index([("user_id", 1), ("status", 1), ("end_at", -1)])
    await subscriptions_col.create_index("end_at")

    # +++ خط جدید (خیلی مهم برای سرعت) +++
    # این باعث میشه وقتی دنبال یه کانفیگ خاص میگردی، آنی پیداش کنه
    await subscriptions_col.create_index("uuid", unique=True)

    # === payments ===
    await payments_col.create_index([("order_id", 1), ("status", 1), ("created_at", -1)])
    await payments_col.create_index("status")

    # === admins ===
    await admins_col.create_index("uid", unique=True)
