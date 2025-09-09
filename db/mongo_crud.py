# db/mongo_crud.py
from datetime import datetime, timedelta
from bson import ObjectId, Int64
from db.mongo import users_col, plans_col, orders_col, subscriptions_col, admins_col

# ---- Users
async def get_or_create_user(tg_id: int, username: str | None, first_name: str | None):
    u = await users_col.find_one({"tg_id": tg_id})
    if u:
        # نرمال‌سازی tg_id به Int64 همزمان با آپدیت
        await users_col.update_one(
            {"_id": u["_id"]},
            {"$set": {
                "tg_id": Int64(tg_id),
                "username": username,
                "first_name": first_name,
            }}
        )
        return u

    doc = {
        "tg_id": Int64(tg_id),            # ← خیلی مهم
        "username": username,
        "first_name": first_name,
        "created_at": datetime.utcnow(),
    }
    res = await users_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

# ---- Plans
DEFAULT_PLANS = [
    {"code": "plan_mini",     "title": "مینی",        "gb": 10,  "days": 30, "devices": 1, "price_toman": 39000,  "active": True},
    {"code": "plan_eco",      "title": "اقتصادی",     "gb": 30,  "days": 30, "devices": 1, "price_toman": 69000,  "active": True},
    {"code": "plan_eco_plus", "title": "Eco+",        "gb": 50,  "days": 30, "devices": 2, "price_toman": 99000,  "active": True},
    {"code": "plan_std1",     "title": "استاندارد ۱", "gb": 70,  "days": 30, "devices": 2, "price_toman": 119000, "active": True},
    {"code": "plan_std2",     "title": "استاندارد ۲", "gb": 100, "days": 30, "devices": 2, "price_toman": 149000, "active": True},
    {"code": "plan_std_plus", "title": "استاندارد+",  "gb": 150, "days": 30, "devices": 3, "price_toman": 199000, "active": True},
]

async def ensure_default_plans():
    existing = {p["code"] async for p in plans_col.find({}, {"code": 1})}
    to_insert = [p for p in DEFAULT_PLANS if p["code"] not in existing]
    if to_insert:
        await plans_col.insert_many(to_insert)

async def get_plan_by_code(code: str):
    return await plans_col.find_one({"code": code, "active": True})

# ---- Orders
async def create_order(user_id: ObjectId, plan_code: str, amount_toman: int, metadata: dict | None = None):
    doc = {
        "user_id": user_id,
        "plan_code": plan_code,
        "amount_toman": amount_toman,
        "status": "pending",
        "provider": None,
        "provider_ref": None,
        "metadata": metadata or {},
        "created_at": datetime.utcnow(),
        "paid_at": None,
    }
    res = await orders_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

async def mark_order_paid(order_id: ObjectId, provider: str, provider_ref: str):
    await orders_col.update_one(
        {"_id": order_id},
        {"$set": {
            "status": "paid",
            "provider": provider,
            "provider_ref": provider_ref,
            "paid_at": datetime.utcnow()
        }}
    )

# ---- Subscriptions
async def create_subscription_from_plan(user_id: ObjectId, order_id: ObjectId, plan: dict, config_ref: str | None = None):
    doc = {
        "user_id": user_id,
        "order_id": order_id,
        "source_plan": plan["code"],
        "gb_total": plan["gb"],
        "gb_used": 0,
        "devices": plan["devices"],
        "start_at": datetime.utcnow(),
        "end_at": datetime.utcnow() + timedelta(days=plan["days"]),
        "status": "active",
        "config_ref": config_ref,
    }
    res = await subscriptions_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

# ---- Admins
# ساختار: {uid:int, username:str|None, added_by:int|None, added_at:datetime}
async def add_admin(uid: int, username: str | None = None, added_by: int | None = None) -> bool:
    if await admins_col.find_one({"uid": uid}):
        return False
    await admins_col.insert_one({
        "uid": uid,
        "username": username,
        "added_by": added_by,
        "added_at": datetime.utcnow(),
    })
    return True

async def remove_admin(uid: int) -> bool:
    res = await admins_col.delete_one({"uid": uid})
    return res.deleted_count > 0

async def list_admins():
    cursor = admins_col.find({})
    return [doc async for doc in cursor]

async def is_admin_db(uid: int) -> bool:
    return await admins_col.find_one({"uid": uid}) is not None
