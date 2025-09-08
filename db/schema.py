# db/schema.py
from db.mongo import db, users_col, plans_col, orders_col, subscriptions_col

# --- Validators ---
USERS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["tg_id", "created_at"],
        "properties": {
            "tg_id": {"bsonType": "long"},
            "username": {"bsonType": ["string", "null"]},
            "first_name": {"bsonType": ["string", "null"]},
            "created_at": {"bsonType": "date"},
        },
    }
}

PLANS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["code", "title", "gb", "days", "devices", "price_toman", "active"],
        "properties": {
            "code": {"bsonType": "string"},
            "title": {"bsonType": "string"},
            "gb": {"bsonType": "int", "minimum": 1},
            "days": {"bsonType": "int", "minimum": 1},
            "devices": {"bsonType": "int", "minimum": 1},
            "price_toman": {"bsonType": "int", "minimum": 0},
            "active": {"bsonType": "bool"},
        },
    }
}

ORDERS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "plan_code", "amount_toman", "status", "created_at"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "plan_code": {"bsonType": "string"},
            "amount_toman": {"bsonType": "int", "minimum": 0},
            "status": {"enum": ["pending", "paid", "failed", "expired", "refunded"]},
            "created_at": {"bsonType": "date"},
        },
    }
}

SUBS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "source_plan", "quota_mb", "used_mb", "devices", "start_at", "end_at", "status"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "source_plan": {"bsonType": "string"},
            "quota_mb": {"bsonType": "int", "minimum": 1},
            "used_mb": {"bsonType": "int", "minimum": 0},
            "devices": {"bsonType": "int", "minimum": 1},
            "start_at": {"bsonType": "date"},
            "end_at": {"bsonType": "date"},
            "status": {"enum": ["active", "suspended", "expired"]},
        },
    }
}

# --- ایندکس‌ها ---
INDEX_SPECS = [
    (users_col, [("tg_id", 1)], {"unique": True}),
    (plans_col, [("code", 1)], {"unique": True}),
    (orders_col, [("user_id", 1), ("status", 1)], {}),
    (subscriptions_col, [("user_id", 1), ("status", 1)], {}),
    (subscriptions_col, [("end_at", 1)], {}),
]

async def ensure_collections_and_validators():
    # ساخت کالکشن‌ها (اگر وجود نداشت)
    try:
        await db.create_collection("users", validator=USERS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "users", "validator": USERS_VALIDATOR, "validationAction": "error"})

    try:
        await db.create_collection("plans", validator=PLANS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "plans", "validator": PLANS_VALIDATOR, "validationAction": "error"})

    try:
        await db.create_collection("orders", validator=ORDERS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "orders", "validator": ORDERS_VALIDATOR, "validationAction": "error"})

    try:
        await db.create_collection("subscriptions", validator=SUBS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "subscriptions", "validator": SUBS_VALIDATOR, "validationAction": "error"})

    # ایندکس‌ها
    for col, keys, opts in INDEX_SPECS:
        await col.create_index(keys, **opts)
