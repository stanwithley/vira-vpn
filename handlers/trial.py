# handlers/trial.py
from aiogram import Router, types, F
from aiogram.types import BufferedInputFile
from datetime import datetime, timedelta

from db.mongo_crud import get_or_create_user
from db.mongo import subscriptions_col
from services.xray_service import add_client
from services.qrcode_gen import make_qr_png_bytes

def rtl(s: str) -> str: return "\u200F" + s
def fa_num(s: str) -> str:
    tbl = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(s).translate(tbl)

router = Router()

# تعداد دستگاه واقعاً enforce می‌شود (برای هر device یک UUID/لینک جدا)
TRIAL_CONF = {
    "quota_mb": 300,   # مگابایت
    "hours": 24,       # ساعت
    "devices": 1,      # اگر 2 یا بیشتر بگذاری، به همان تعداد لینک/QR می‌سازیم
}

def _fmt_trial_msg(links: list[str], end_at: datetime) -> str:
    header = rtl(
        "✅ اکانت تست فعال شد.\n\n"
        f"• حجم: {fa_num(TRIAL_CONF['quota_mb'])} مگ\n"
        f"• مدت: {fa_num(TRIAL_CONF['hours'])} ساعت\n"
        f"• دستگاه: {fa_num(TRIAL_CONF['devices'])}\n"
        f"• پایان: {end_at:%Y-%m-%d %H:%M UTC}\n"
        "—\n"
        "🔗 لینک‌های اتصال:"
    )
    lines = [header]
    for i, link in enumerate(links, 1):
        lines.append(f"{i}) <code>{link}</code>")
    lines.append(rtl("\nهر دستگاه از یکی از لینک‌ها استفاده کند."))
    return "\n".join(lines)

async def _ensure_trial_links(user_id: int, sub_id, dev_count: int) -> tuple[list[str], list[dict]]:
    """
    مطمئن می‌شود برای اشتراک تِست، به تعداد devices لینک/UUID وجود دارد.
    اگر نبود، می‌سازد و در DB ذخیره می‌کند.
    خروجی: (links, xray_accounts)
    """
    doc = await subscriptions_col.find_one({"_id": sub_id})
    links = doc.get("config_ref")
    xinfo = doc.get("xray")

    # نرمالایز به ساختار جدید: links = list[str] و xray = list[{"email","uuid"}]
    if isinstance(links, str):
        links = [links]
    elif not isinstance(links, list):
        links = []

    accounts: list[dict] = []
    if isinstance(xinfo, dict) and ("email" in xinfo or "uuid" in xinfo):
        accounts = [xinfo]
    elif isinstance(xinfo, list):
        accounts = xinfo
    else:
        accounts = []

    # اضافه کردن تا رسیدن به dev_count
    made_new = False
    i = 0
    while len(links) < dev_count:
        i = len(links) + 1
        email = f"trial-{user_id}-{i}@bot"
        uuid_str, vless_link = add_client(email)
        links.append(vless_link)
        accounts.append({"email": email, "uuid": uuid_str})
        made_new = True

    if made_new:
        await subscriptions_col.update_one(
            {"_id": sub_id},
            {"$set": {"config_ref": links, "xray": accounts}}
        )
    return links, accounts

@router.message(F.text == "🧪 اکانت تست")
async def trial_handler(m: types.Message):
    user = await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name,
    )

    now = datetime.utcnow()
    dev_count = int(TRIAL_CONF["devices"])

    # اگر قبلاً تست فعال دارد و تمام نشده، همان را نشان بده (و در صورت نیاز لینک‌ها را کامل کن)
    existed = await subscriptions_col.find_one({
        "user_id": user["_id"],
        "source_plan": "trial",
        "status": "active",
        "end_at": {"$gt": now},
    })
    if existed:
        links, _ = await _ensure_trial_links(m.from_user.id, existed["_id"], dev_count)

        # ارسال QR چندتایی
        media = []
        for i, link in enumerate(links, 1):
            png = make_qr_png_bytes(link)
            media.append(types.InputMediaPhoto(
                media=BufferedInputFile(png, filename=f"trial_{i}.png"),
                caption=_fmt_trial_msg(links, existed["end_at"]) if i == 1 else None,
                parse_mode="HTML"
            ))
        if media:
            await m.answer_media_group(media)
        else:
            await m.answer(_fmt_trial_msg(links, existed["end_at"]), parse_mode="HTML")
        return

    # ساخت تِست جدید
    end_at = now + timedelta(hours=TRIAL_CONF["hours"])
    links = []
    accounts = []
    for i in range(dev_count):
        email = f"trial-{m.from_user.id}-{i+1}@bot"
        uuid_str, vless_link = add_client(email)
        links.append(vless_link)
        accounts.append({"email": email, "uuid": uuid_str})

    sub_doc = {
        "user_id": user["_id"],
        "order_id": None,
        "source_plan": "trial",
        "quota_mb": TRIAL_CONF["quota_mb"],
        "used_mb": 0,
        "devices": dev_count,
        "start_at": now,
        "end_at": end_at,
        "status": "active",
        "config_ref": links,   # لیست لینک‌ها
        "xray": accounts,      # لیست ایمیل/UUID
    }
    res = await subscriptions_col.insert_one(sub_doc)

    # QR چندتایی
    media = []
    for i, link in enumerate(links, 1):
        png = make_qr_png_bytes(link)
        media.append(types.InputMediaPhoto(
            media=BufferedInputFile(png, filename=f"trial_{i}.png"),
            caption=_fmt_trial_msg(links, end_at) if i == 1 else None,
            parse_mode="HTML"
        ))
    if media:
        await m.answer_media_group(media)
    else:
        await m.answer(_fmt_trial_msg(links, end_at), parse_mode="HTML")
