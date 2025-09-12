# db/mongo_crud.py
from datetime import datetime, timedelta
from bson import ObjectId, Int64
from typing import Any, Literal, TypedDict

from db.mongo import users_col, plans_col, orders_col, subscriptions_col, admins_col, payments_col

# ---- Users
async def get_or_create_user(tg_id: int, username: str | None, first_name: str | None):
    # اختلاف نوع int/Int64 را پوشش بده
    u = await users_col.find_one({"tg_id": {"$in": [tg_id, Int64(tg_id)]}})
    if u:
        await users_col.update_one(
            {"_id": u["_id"]},
            {"$set": {
                "tg_id": Int64(tg_id),
                "username": username,
                "first_name": first_name,
            }}
        )
        u["tg_id"] = Int64(tg_id)
        u["username"] = username
        u["first_name"] = first_name
        return u

    doc = {
        "tg_id": Int64(tg_id),
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
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "order_id": order_id,
        "source_plan": plan["code"],
        "quota_mb": int(plan["gb"]) * 1024,   # به MB
        "used_mb": 0,
        "devices": plan["devices"],
        "start_at": now,
        "end_at": now + timedelta(days=plan["days"]),
        "status": "active",
        "config_ref": config_ref,
    }
    res = await subscriptions_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

# ---- Admins
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

# ========= Helpers =========
def _to_object_id(x) -> ObjectId:
    if isinstance(x, ObjectId):
        return x
    return ObjectId(str(x))

# ========= Orders (تکمیلی) =========
async def get_order(order_id: ObjectId | str) -> dict | None:
    return await orders_col.find_one({"_id": _to_object_id(order_id)})

async def update_order_status(order_id: ObjectId | str, status: Literal["pending", "paid", "canceled", "expired"], **fields):
    update = {"status": status}
    update.update(fields or {})
    await orders_col.update_one({"_id": _to_object_id(order_id)}, {"$set": update})

# ========= Users (تکمیلی) =========
async def get_user_by_id(user_id: ObjectId | str) -> dict | None:
    return await users_col.find_one({"_id": _to_object_id(user_id)})

async def get_user_by_tg_id(tg_id: int) -> dict | None:
    return await users_col.find_one({"tg_id": {"$in": [tg_id, Int64(tg_id)]}})

# ========= Payments =========
class Proof(TypedDict, total=False):
    type: Literal["photo", "document", "text"]
    file_id: str
    text: str
    at: datetime

async def create_payment_request(
    order_id: ObjectId | str,
    method: Literal["c2c", "gateway"],
    due_at: datetime,
    amount_toman: int | None = None,
    meta: dict | None = None,
) -> dict:
    order_id = _to_object_id(order_id)
    order = await get_order(order_id)
    if not order:
        raise ValueError("order not found")

    doc = {
        "order_id": order_id,
        "method": method,
        "amount_toman": int(amount_toman or order["amount_toman"]),
        "status": "pending_proof",
        "created_at": datetime.utcnow(),
        "due_at": due_at,
        "submitted_at": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "provider_ref": None,
        "meta": meta or {},
        "proofs": [],
    }
    res = await payments_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

async def attach_proof_to_payment(
    payment_id: ObjectId | str,
    proof_file_id: str | None,
    proof_text: str | None,
    proof_type: Literal["photo", "document", "text"] | None = None,
) -> bool:
    payment_id = _to_object_id(payment_id)

    proof: Proof = {"at": datetime.utcnow()}
    if proof_file_id:
        proof["type"] = proof_type or "document"
        proof["file_id"] = proof_file_id
    elif proof_text:
        proof["type"] = "text"
        proof["text"] = proof_text
    else:
        return False

    res = await payments_col.update_one(
        {"_id": payment_id},
        {"$push": {"proofs": proof},
         "$set": {"status": "submitted", "submitted_at": datetime.utcnow()}}
    )
    return res.modified_count > 0

async def get_payment_by_id(payment_id: ObjectId | str) -> dict | None:
    return await payments_col.find_one({"_id": _to_object_id(payment_id)})

async def update_payment_status(
    payment_id: ObjectId | str,
    status: Literal["pending_proof", "submitted", "approved", "rejected", "expired"],
    reviewer_uid: int | None = None,
    reason: str | None = None,
    provider_ref: str | None = None,
) -> bool:
    update: dict[str, Any] = {"status": status}

    if status in ("approved", "rejected", "expired"):
        update["reviewed_at"] = datetime.utcnow()
        if reviewer_uid is not None:
            update["reviewed_by"] = reviewer_uid
    if reason:
        update.setdefault("meta", {})
        update["meta"]["reason"] = reason
    if provider_ref:
        update["provider_ref"] = provider_ref

    res = await payments_col.update_one({"_id": _to_object_id(payment_id)}, {"$set": update})
    return res.modified_count > 0

# شورتکات: تایید پرداخت کارت‌به‌کارت + نهایی کردن سفارش
async def approve_c2c_payment_and_mark_order_paid(payment_id: ObjectId | str, reviewer_uid: int | None = None) -> bool:
    payment = await get_payment_by_id(payment_id)
    if not payment:
        return False
    order_id = payment["order_id"]

    ok1 = await update_payment_status(payment_id, "approved", reviewer_uid=reviewer_uid, provider_ref=str(payment["_id"]))
    await mark_order_paid(order_id, provider="c2c", provider_ref=str(payment["_id"]))
    return ok1

# شورتکات: رد پرداخت
async def reject_c2c_payment(payment_id: ObjectId | str, reviewer_uid: int | None = None, reason: str | None = None) -> bool:
    return await update_payment_status(payment_id, "rejected", reviewer_uid=reviewer_uid, reason=reason)

# انقضای پرداخت‌های بازِ یک سفارش (برای انصراف)
async def expire_open_payments_for_order(order_id: ObjectId | str) -> int:
    order_id = _to_object_id(order_id)
    res = await payments_col.update_many(
        {"order_id": order_id, "status": {"$in": ["pending_proof", "submitted"]}},
        {"$set": {"status": "expired", "reviewed_at": datetime.utcnow()}}
    )
    return res.modified_count or 0

# (اختیاری) لیست پرداخت‌ها
async def list_payments(status: Literal["pending_proof", "submitted", "approved", "rejected", "expired"] | None = None, limit: int = 50):
    filt = {}
    if status:
        filt["status"] = status
    cursor = payments_col.find(filt).sort([("created_at", -1)]).limit(limit)
    return [doc async for doc in cursor]
