# db/schema.py
from db.mongo import db, users_col, plans_col, orders_col, subscriptions_col

# --- Validators (قوانین دیتابیس) ---

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
            # فیلدهای اختیاری برای پرداخت
            "provider": {"bsonType": ["string", "null"]},
            "provider_ref": {"bsonType": ["string", "null"]},
            "paid_at": {"bsonType": ["date", "null"]},
        },
    }
}

# اصلاح شده: اضافه شدن فیلدهای پنل (uuid, email)
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

            # === فیلدهای حیاتی برای اتصال به پنل 3x-ui ===
            "uuid": {"bsonType": ["string", "null"]},  # کد کانفیگ (V2Ray ID)
            "email": {"bsonType": ["string", "null"]},  # ایمیل کاربر در پنل
            "config_ref": {"bsonType": ["string", "null"]},  # جهت بکاپ
        },
    }
}

# --- ایندکس‌ها (برای سرعت بالا) ---
INDEX_SPECS = [
    # یوزر تلگرام یکتا باشد
    (users_col, [("tg_id", 1)], {"unique": True}),

    # کد پلن یکتا باشد
    (plans_col, [("code", 1)], {"unique": True}),

    # جستجوی سریع سفارشات
    (orders_col, [("user_id", 1), ("status", 1)], {}),

    # جستجوی سریع اشتراک‌ها
    (subscriptions_col, [("user_id", 1), ("status", 1)], {}),
    (subscriptions_col, [("end_at", 1)], {}),  # برای پیدا کردن منقضی‌ها

    # +++ جدید: جستجوی سریع روی UUID (برای پیدا کردن اشتراک با کد کانفیگ) +++
    (subscriptions_col, [("uuid", 1)], {"unique": True, "sparse": True}),
]


async def ensure_collections_and_validators():
    """
    این تابع کالکشن‌ها را می‌سازد و اگر از قبل وجود داشته باشند،
    قوانین (Validator) جدید را روی آن‌ها اعمال می‌کند.
    """

    # 1. Users
    try:
        await db.create_collection("users", validator=USERS_VALIDATOR, validationAction="error")
    except Exception:
        # اگر کالکشن هست، ولیدیتور را آپدیت کن
        await db.command({"collMod": "users", "validator": USERS_VALIDATOR, "validationAction": "error"})

    # 2. Plans
    try:
        await db.create_collection("plans", validator=PLANS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "plans", "validator": PLANS_VALIDATOR, "validationAction": "error"})

    # 3. Orders
    try:
        await db.create_collection("orders", validator=ORDERS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "orders", "validator": ORDERS_VALIDATOR, "validationAction": "error"})

    # 4. Subscriptions
    try:
        await db.create_collection("subscriptions", validator=SUBS_VALIDATOR, validationAction="error")
    except Exception:
        await db.command({"collMod": "subscriptions", "validator": SUBS_VALIDATOR, "validationAction": "error"})

    # ساخت ایندکس‌ها
    for col, keys, opts in INDEX_SPECS:
        # برای جلوگیری از ارور تکراری بودن نام ایندکس، از try-except ساده استفاده می‌کنیم
        try:
            await col.create_index(keys, **opts)
        except Exception as e:
            print(f"Warning creating index for {col.name}: {e}")