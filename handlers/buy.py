# handlers/buy.py
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.mongo_crud import get_or_create_user, get_plan_by_code, create_order

router = Router()

# ===== تنظیمات =====
SHOW_HEADER = True
SEP = " · "
INV = "\u2063"  # متن نامرئی معتبر تلگرام

# ===== کمکی‌ها =====
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def fa_num(s: str) -> str: return s.translate(PERSIAN_DIGITS)
def rtl(s: str) -> str: return "\u200F" + s
def fmt_price(toman: int) -> str: return fa_num(f"{toman:,}") + " ت"

def button_label(gb: int, days: int, devices: int, price_t: int) -> str:
    # بدون اسم و سرعت؛ جمع‌وجور برای دکمه
    parts = [
        f"💎 {fa_num(str(gb))}گیگ",
        f"🗓 {fa_num(str(days))}روز",
        f"🖥 {fa_num(str(devices))}",
        f"💰 {fmt_price(price_t)}",
    ]
    return rtl(SEP.join(parts))

# ===== داده‌ها =====
PLANS = [
    {"key": "plan_mini",     "title": "💠 مینی",        "gb": 10,  "days": 30, "dev": 1, "price": 39000},
    {"key": "plan_eco",      "title": "💠 اقتصادی",     "gb": 30,  "days": 30, "dev": 1, "price": 69000},
    {"key": "plan_eco_plus", "title": "💠 Eco+",        "gb": 50,  "days": 30, "dev": 2, "price": 99000},
    {"key": "plan_std1",     "title": "💠 استاندارد ۱", "gb": 70,  "days": 30, "dev": 2, "price": 119000},
    {"key": "plan_std2",     "title": "💠 استاندارد ۲", "gb": 100, "days": 30, "dev": 2, "price": 149000},
    {"key": "plan_std_plus", "title": "💠 استاندارد+",  "gb": 150, "days": 30, "dev": 3, "price": 199000},
]

# ===== کیبوردها =====
def build_plans_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in PLANS:
        kb.button(
            text=button_label(p["gb"], p["days"], p["dev"], p["price"]),
            callback_data=p["key"]
        )
    kb.button(text=rtl("⚙️ پلن کاستوم"), callback_data="plan_custom")
    kb.button(text=rtl("⬅️ بازگشت"), callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()

def build_plan_actions_kb(key: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("🧾 خرید این پلن"), callback_data=f"buy:{key}")
    kb.button(text=rtl("⬅️ بازگشت"), callback_data="back_to_plans")
    kb.adjust(1)
    return kb.as_markup()

def build_custom_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("🛠 ساخت پلن کاستوم"), callback_data="custom_build")
    kb.button(text=rtl("⬅️ بازگشت"), callback_data="back_to_plans")
    kb.adjust(1)
    return kb.as_markup()

HEADER = rtl("🎁 لطفاً یکی از سرویس‌ها را انتخاب کنید:")

# ===== ورود به خرید =====
@router.message(F.text == "🛒 خرید اشتراک")
async def buy_entry(m: types.Message):
    await m.answer(HEADER if SHOW_HEADER else INV, reply_markup=build_plans_kb())

# ===== کلیک روی پلن‌ها / کاستوم =====
@router.callback_query(F.data.in_([p["key"] for p in PLANS] + ["plan_custom"]))
async def on_plan_clicked(cq: types.CallbackQuery):
    data = cq.data
    if data == "plan_custom":
        text = rtl(
            "⚙️ پلن کاستوم\n\n"
            "• پایه: ۱۰ گیگ / ۱ ماه / ۱ دستگاه → ۴۰,۰۰۰ ت\n"
            "• هر ۱۰ گیگ اضافه: +۱۵,۰۰۰\n"
            "• هر دستگاه اضافه: +۲۰,۰۰۰\n"
            "• پروتکل کامل (WG + Hysteria2 + VLESS/REALITY): +۴۹,۰۰۰\n\n"
            "📆 مدت‌های طولانی‌تر با تخفیف: ۳ ماه ×۲.۵ | ۶ ماه ×۴.۵ | ۱۲ ماه ×۸"
        )
        await cq.message.edit_text(text, reply_markup=build_custom_kb())
        return await cq.answer()

    p = next(p for p in PLANS if p["key"] == data)
    # صفحه‌ی جزئیات با تایتل و آیتم‌ها
    details = rtl(
        f"{p['title']}\n\n"
        f"• حجم: {fa_num(str(p['gb']))} گیگ\n"
        f"• مدت: {fa_num(str(p['days']))} روزه\n"
        f"• دستگاه: {fa_num(str(p['dev']))}\n"
        f"• قیمت: {fmt_price(p['price'])}"
    )
    await cq.message.edit_text(details, reply_markup=build_plan_actions_kb(p["key"]))
    await cq.answer()

# ===== برگشت‌ها =====
@router.callback_query(F.data == "back_to_plans")
async def back_to_plans(cq: types.CallbackQuery):
    await cq.message.edit_text(HEADER if SHOW_HEADER else INV, reply_markup=build_plans_kb())
    await cq.answer()

@router.callback_query(F.data == "back_main")
async def back_main(cq: types.CallbackQuery):
    # TODO: منوی اصلی خودت رو بگذار
    await cq.message.edit_text(rtl("✅ به منوی اصلی برگشتی."))
    await cq.answer()

# ===== خرید (استاب) =====
@router.callback_query(F.data.startswith("buy:"))
async def on_buy_plan(cq: types.CallbackQuery):
    key = cq.data.split(":", 1)[1]

    # گرفتن user + plan از Mongo
    user = await get_or_create_user(cq.from_user.id, cq.from_user.username, cq.from_user.first_name)
    plan = await get_plan_by_code(key)
    if not plan:
        return await cq.answer("\u200Fپلن نامعتبر یا غیرفعال است.", show_alert=True)

    order = await create_order(user_id=user["_id"], plan_code=plan["code"], amount_toman=plan["price_toman"])

    # پیام تایید سفارش (فعلاً بدون درگاه)
    await cq.message.edit_text(
        "\u200F"
        f"🧾 سفارش ثبت شد (#{str(order['_id'])[-6:]})\n"
        f"• پلن: {plan['title']}\n"
        f"• مبلغ: {format(plan['price_toman'], ',')} ت\n\n"
        "درگاه پرداخت به‌زودی متصل می‌شود.",
        reply_markup=build_plan_actions_kb(key)
    )
    await cq.answer()
