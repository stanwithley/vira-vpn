# handlers/trial.py
from aiogram import Router, types, F
from aiogram.types import BufferedInputFile
from datetime import datetime, timedelta

from db.mongo_crud import get_or_create_user
from db.mongo import subscriptions_col
from services.xray_service import add_client
from services.qrcode_gen import make_qr_png_bytes

# اگر utilهای قالب‌بندی فارسی داری از همان‌ها استفاده کن؛
# اینجا یک RTL ساده می‌گذارم تا وابستگی نشود.
def rtl(s: str) -> str: return "\u200F" + s
def fa_num(s: str) -> str:
    tbl = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(s).translate(tbl)

router = Router()

TRIAL_CONF = {
    "quota_mb": 300,   # ۳۰۰ مگابایت
    "hours": 24,       # ۲۴ ساعت
    "devices": 1,
}

def _fmt_trial_msg(vless_uri: str, end_at: datetime) -> str:
    return rtl(
        "✅ اکانت تست فعال شد.\n\n"
        f"• حجم: {fa_num(TRIAL_CONF['quota_mb'])} مگ\n"
        f"• مدت: {fa_num(TRIAL_CONF['hours'])} ساعت\n"
        f"• دستگاه: {fa_num(TRIAL_CONF['devices'])}\n"
        f"• پایان: {end_at:%Y-%m-%d %H:%M UTC}\n"
        "—\n"
        "🔗 لینک اتصال (کپی کن داخل v2rayN/v2rayNG/Nekoray وارد کن):\n"
        f"<code>{vless_uri}</code>\n\n"
        "یا QR را اسکن کن."
    )

@router.message(F.text == "🧪 اکانت تست")
async def trial_handler(m: types.Message):
    user = await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name,
    )

    now = datetime.utcnow()

    # اگر قبلاً تِست فعال دارد و تمام نشده، همان را نمایش بده
    existed = await subscriptions_col.find_one({
        "user_id": user["_id"],
        "source_plan": "trial",
        "status": "active",
        "end_at": {"$gt": now},
    })
    if existed:
        vless = existed.get("config_ref")
        if not vless:
            # اگر قدیمی بوده و لینک ذخیره نشده؛ از ایمیلِ ثبت‌شده re-generate کنیم
            xinfo = existed.get("xray") or {}
            email = xinfo.get("email") or f"trial-{m.from_user.id}@bot"
            uuid_str = xinfo.get("uuid")
            # اگر uuid نداریم، add_client ایمیل قبلی را reuse می‌کند یا جدید می‌سازد
            uuid_str, vless = add_client(email)
            await subscriptions_col.update_one(
                {"_id": existed["_id"]},
                {"$set": {"config_ref": vless, "xray.uuid": uuid_str, "xray.email": email}}
            )
        png = make_qr_png_bytes(vless)
        await m.answer_photo(
            photo=BufferedInputFile(png, filename="trial.png"),
            caption=_fmt_trial_msg(vless, existed["end_at"]),
            parse_mode="HTML"
        )
        return

    # در غیر این صورت، یک تست جدید ایجاد کن
    end_at = now + timedelta(hours=TRIAL_CONF["hours"])

    # ایمیل/برچسب یکتا برای Xray (قابل سرچ در لاگ‌ها)
    email = f"trial-{m.from_user.id}@bot"

    # روی Xray کاربر را اضافه کن و لینک VLESS بده
    uuid_str, vless_link = add_client(email)

    # اشتراک را در DB ذخیره کن
    sub_doc = {
        "user_id": user["_id"],
        "order_id": None,
        "source_plan": "trial",
        "quota_mb": TRIAL_CONF["quota_mb"],  # MB
        "used_mb": 0,
        "devices": TRIAL_CONF["devices"],
        "start_at": now,
        "end_at": end_at,
        "status": "active",
        "config_ref": vless_link,
        "xray": {"email": email, "uuid": uuid_str},
    }
    await subscriptions_col.insert_one(sub_doc)

    # QR بساز و ارسال کن
    png = make_qr_png_bytes(vless_link)
    await m.answer_photo(
        photo=BufferedInputFile(png, filename="trial.png"),
        caption=_fmt_trial_msg(vless_link, end_at),
        parse_mode="HTML"
    )
