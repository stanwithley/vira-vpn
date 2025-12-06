# handlers/trial.py
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.types import BufferedInputFile, InputMediaPhoto

from db.mongo import subscriptions_col
from db.mongo_crud import get_or_create_user
from services.qrcode_gen import make_qr_png_bytes
# تغییر مهم: ایمپورت کلاس جدید
from services.xray_service import XrayService
from config import settings


def rtl(s: str) -> str: return "\u200F" + s


def fa_num(s: str) -> str:
    tbl = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(s).translate(tbl)


router = Router()

# تنظیمات تست رایگان
TRIAL_CONF = {
    "quota_mb": 500,  # مگابایت
    "hours": 24,  # ساعت
    "limit_ip": 1  # تعداد کاربر همزمان
}

# نمونه‌سازی از سرویس پنل
xray = XrayService()


def _fmt_trial_msg(links: list[str], sub_link: str, end_at: datetime) -> str:
    header = rtl(
        "✅ اکانت تست فعال شد.\n\n"
        f"• حجم: {fa_num(TRIAL_CONF['quota_mb'])} مگ\n"
        f"• مدت: {fa_num(TRIAL_CONF['hours'])} ساعت\n"
        f"• پایان: {end_at:%Y-%m-%d %H:%M}\n"
        "—\n"
    )

    body = []
    # 1. لینک اشتراک (مهمترین)
    if sub_link:
        body.append(rtl("🔄 <b>لینک اشتراک (هوشمند):</b>"))
        body.append(f"<code>{sub_link}</code>\n")

    # 2. لینک اتصال مستقیم
    if links:
        body.append(rtl("🔗 <b>لینک اتصال مستقیم:</b>"))
        for i, link in enumerate(links, 1):
            body.append(f"<code>{link}</code>")

    body.append(rtl("\nنکته: برای اتصال بهتر، از لینک اشتراک استفاده کنید."))

    return header + "\n".join(body)


async def _send_links_with_qr(m: types.Message, links: list[str], sub_link: str, end_at: datetime):
    caption = _fmt_trial_msg(links, sub_link, end_at)

    # اولویت QR با لینک اشتراک است، اگر نبود لینک اول
    qr_target = sub_link if sub_link else (links[0] if links else None)

    if not qr_target:
        await m.answer(caption, parse_mode="HTML")
        return

    try:
        qr_bytes = make_qr_png_bytes(qr_target)
        await m.answer_photo(
            photo=BufferedInputFile(qr_bytes, filename="trial_qr.png"),
            caption=caption,
            parse_mode="HTML"
        )
    except Exception:
        await m.answer(caption, parse_mode="HTML")


@router.message(F.text == "🧪 اکانت تست")
async def trial_handler(m: types.Message):
    user = await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name,
    )

    now = datetime.utcnow()

    # 1. بررسی اینکه آیا قبلاً تست گرفته؟ (فعال یا منقضی مهم نیست، هر نفر یک بار)
    # اگر می‌خواهید بعد از انقضا دوباره بتواند بگیرد، شرط status را بردارید
    existed = await subscriptions_col.find_one({
        "user_id": user["_id"],
        "source_plan": "trial"
    })

    if existed:
        # اگر تست قبلاً گرفته، لینک‌هاش رو نشون بده (یا بگو تموم شده)
        if existed.get("end_at") > now and existed.get("status") == "active":
            # هنوز فعاله، دوباره براش بفرست
            uuid_str = existed.get("uuid")
            # بازسازی لینک‌ها
            sub_link = f"{settings.PANEL_URL.rstrip('/')}/sub/{uuid_str}"
            vless_link = xray._generate_vless_link(uuid_str, existed.get("email", "trial"))

            await m.answer(rtl("شما قبلاً اکانت تست فعال دارید. اطلاعات آن:"))
            await _send_links_with_qr(m, [vless_link], sub_link, existed["end_at"])
        else:
            await m.answer(rtl("❌ شما قبلاً از اکانت تست استفاده کرده‌اید. لطفاً اشتراک تهیه کنید."))
        return

    # 2. ساخت تست جدید
    wait_msg = await m.answer(rtl("⏳ در حال ساخت اکانت تست..."))

    email = f"trial-{m.from_user.id}-{int(datetime.now().timestamp())}"
    end_at = now + timedelta(hours=TRIAL_CONF["hours"])

    # محاسبه روز (برای تابع add_client که روز میگیره)
    # چون تابع روز میگیره و ما ساعت میخوایم، باید تبدیل کنیم یا تابع رو تغییر بدیم
    # فعلا 1 روز میزنیم ولی Expire Time رو دستی ست میکنیم
    days = 1

    # درخواست به پنل
    result = await xray.add_client(
        email=email,
        limit_ip=TRIAL_CONF["limit_ip"],
        total_gb=TRIAL_CONF["quota_mb"] / 1024,  # تبدیل مگ به گیگ (چون تابع گیگ میگیره)
        expire_days=days
    )

    if not result:
        await wait_msg.edit_text(rtl("❌ خطا در ارتباط با سرور. لطفاً بعداً تلاش کنید."))
        return

    uuid_str = result["uuid"]
    vless_link = result["link"]

    # لینک اشتراک
    sub_link = f"{settings.PANEL_URL.rstrip('/')}/sub/{uuid_str}"

    # ذخیره در دیتابیس
    sub_doc = {
        "user_id": user["_id"],
        "order_id": None,
        "source_plan": "trial",
        "quota_mb": TRIAL_CONF["quota_mb"],
        "used_mb": 0,
        "devices": TRIAL_CONF["limit_ip"],
        "start_at": now,
        "end_at": end_at,
        "status": "active",

        # فیلدهای جدید
        "uuid": uuid_str,
        "email": email,
        "config_ref": [vless_link]
    }
    await subscriptions_col.insert_one(sub_doc)

    await wait_msg.delete()
    await _send_links_with_qr(m, [vless_link], sub_link, end_at)