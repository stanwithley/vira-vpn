# db/mongo.py
import motor.motor_asyncio
from datetime import datetime
from config import settings

client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

users_col         = db["users"]
plans_col         = db["plans"]
orders_col        = db["orders"]
subscriptions_col = db["subscriptions"]

async def ensure_indexes():
    # کاربران
    await users_col.create_index("tg_id", unique=True)

    # پلن‌ها
    await plans_col.create_index("code", unique=True)
    await plans_col.create_index([("active", 1)])

    # سفارش‌ها
    await orders_col.create_index([("user_id", 1), ("status", 1)])
    await orders_col.create_index("created_at")

    # اشتراک‌ها
    await subscriptions_col.create_index([("user_id", 1), ("status", 1)])
    await subscriptions_col.create_index("end_at")
