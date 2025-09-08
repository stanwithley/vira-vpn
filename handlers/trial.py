# handlers/trial.py
from aiogram import Router, types, F
from datetime import datetime, timedelta
from db.mongo_crud import get_or_create_user
from db.mongo import subscriptions_col
from utils.locale import rtl, fa_num, fmt_dt

router = Router()

TRIAL_CONF = {
    "quota_mb": 300,  # ۳۰۰ مگابایت
    "hours": 24,      # ۲۴ ساعت
    "devices": 1,
}

@router.message(F.text == "🧪 اکانت تست")
async def trial_handler(m: types.Message):
    user = await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name,
    )

    existed = await subscriptions_col.find_one({"user_id": user["_id"], "source_plan": "trial"})
    if existed:
        return await m.answer(rtl("⚠️ شما قبلاً از اکانت تست استفاده کرده‌اید."))

    now = datetime.utcnow()
    doc = {
        "user_id": user["_id"],
        "order_id": None,
        "source_plan": "trial",
        "quota_mb": TRIAL_CONF["quota_mb"],
        "used_mb": 0,
        "devices": TRIAL_CONF["devices"],
        "start_at": now,
        "end_at": now + timedelta(hours=TRIAL_CONF["hours"]),
        "status": "active",
        "config_ref": None,
    }
    res = await subscriptions_col.insert_one(doc)

    text = rtl(
        "✅ اکانت تست فعال شد.\n\n"
        f"• حجم: {fa_num(TRIAL_CONF['quota_mb'])} مگ\n"
        f"• مدت: {fa_num(TRIAL_CONF['hours'])} ساعت\n"
        f"• دستگاه: {fa_num(TRIAL_CONF['devices'])}\n"
        f"• شروع: {fmt_dt(now)}\n"
        f"• پایان: {fmt_dt(doc['end_at'])}\n"
        f"• شناسه: #{str(res.inserted_id)[-6:]}\n\n"
        "برای پلن کامل، از «🛒 خرید اشتراک» استفاده کنید."
    )
    await m.answer(text)
