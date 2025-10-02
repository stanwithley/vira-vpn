# handlers/buy.py
from datetime import datetime, timedelta

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from db.mongo_crud import (
    get_or_create_user, get_plan_by_code, create_order, get_order,
    update_order_status,  # برای cancel
    create_payment_request, attach_proof_to_payment,
    get_payment_by_id, get_user_by_id,
    approve_c2c_payment_and_mark_order_paid, reject_c2c_payment,
    expire_open_payments_for_order,
)

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
    parts = [
        f"💎 {fa_num(str(gb))}گیگ",
        f"🗓 {fa_num(str(days))}روز",
        f"🖥 {fa_num(str(devices))}",
        f"💰 {fmt_price(price_t)}",
    ]
    return rtl(SEP.join(parts))


async def safe_edit(message: types.Message, text: str | None = None, caption: str | None = None, **kwargs):
    """اگر پیام کپشن داشت، ویرایش کپشن؛ اگر نداشت ویرایش متن."""
    try:
        if message.caption is not None:
            return await message.edit_caption(caption=caption or text, **kwargs)
        else:
            return await message.edit_text(text=text or caption, **kwargs)
    except Exception:
        return await message.answer(text or caption or "", **kwargs)


# ===== داده‌ها =====
PLANS = [
    {"key": "plan_mini", "title": "💠 مینی", "gb": 10, "days": 30, "dev": 1, "price": 39000},
    {"key": "plan_eco", "title": "💠 اقتصادی", "gb": 30, "days": 30, "dev": 1, "price": 69000},
    {"key": "plan_eco_plus", "title": "💠 Eco+", "gb": 50, "days": 30, "dev": 2, "price": 99000},
    {"key": "plan_std1", "title": "💠 استاندارد ۱", "gb": 70, "days": 30, "dev": 2, "price": 119000},
    {"key": "plan_std2", "title": "💠 استاندارد ۲", "gb": 100, "days": 30, "dev": 2, "price": 149000},
    {"key": "plan_std_plus", "title": "💠 استاندارد+", "gb": 150, "days": 30, "dev": 3, "price": 199000},
]


# ===== کیبوردها =====
def build_plans_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in PLANS:
        kb.button(text=button_label(p["gb"], p["days"], p["dev"], p["price"]), callback_data=p["key"])
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


def build_after_order_kb(order_id: str, plan_key: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("💳 پرداخت کارت‌به‌کارت"), callback_data=f"pay_c2c:{order_id}")
    kb.button(text=rtl("⬅️ تغییر پلن"), callback_data=f"change_plan:{order_id}")
    kb.button(text=rtl("❌ انصراف"), callback_data=f"cancel_order:{order_id}")
    kb.button(text=rtl("🛟 پشتیبانی"), url=f"https://t.me/{settings.SUPPORT_USERNAME.lstrip('@')}")
    kb.adjust(1)
    return kb.as_markup()


def build_back_to_after_order_kb(order_id: str, plan_key: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("⬅️ برگشت به پرداخت"), callback_data=f"after_order:{order_id}:{plan_key}")
    kb.adjust(1)
    return kb.as_markup()


def build_admin_decision_kb(payment_id: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تایید", callback_data=f"approve_payment:{payment_id}")
    kb.button(text="❌ رد", callback_data=f"reject_payment:{payment_id}")
    kb.adjust(2)
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
            "📆 مدت‌های طولانی‌تر با تخفیف: ۳ ماه %۲.۵ | ۶ ماه %۴.۵ | ۱۲ ماه %۸"
        )
        await cq.message.edit_text(text, reply_markup=build_custom_kb())
        return await cq.answer()

    p = next(p for p in PLANS if p["key"] == data)
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
    await cq.message.edit_text(rtl("✅ به منوی اصلی برگشتی."))
    await cq.answer()


# ===== خرید → ثبت سفارش =====
@router.callback_query(F.data.startswith("buy:"))
async def on_buy_plan(cq: types.CallbackQuery):
    key = cq.data.split(":", 1)[1]

    user = await get_or_create_user(cq.from_user.id, cq.from_user.username, cq.from_user.first_name)
    plan = await get_plan_by_code(key)
    if not plan:
        return await cq.answer("\u200Fپلن نامعتبر یا غیرفعال است.", show_alert=True)

    order = await create_order(user_id=user["_id"], plan_code=plan["code"], amount_toman=plan["price_toman"])

    await cq.message.edit_text(
        "\u200F"
        f"🧾 سفارش ثبت شد (#{str(order['_id'])[-6:]})\n"
        f"• پلن: {plan['title']}\n"
        f"• مبلغ: {format(plan['price_toman'], ',')} ت\n\n"
        "روش پرداخت را انتخاب کنید:",
        reply_markup=build_after_order_kb(str(order["_id"]), key)
    )
    await cq.answer()


# ===== صفحه بعد از سفارش =====
@router.callback_query(F.data.startswith("after_order:"))
async def on_after_order(cq: types.CallbackQuery):
    _, order_id, plan_key = cq.data.split(":")
    await cq.message.edit_text(
        rtl("لطفاً روش پرداخت را انتخاب کنید:"),
        reply_markup=build_after_order_kb(order_id, plan_key)
    )
    await cq.answer()


# ===== تغییر پلن =====
@router.callback_query(F.data.startswith("change_plan:"))
async def on_change_plan(cq: types.CallbackQuery):
    # (اختیاری) می‌تونی سفارش قبلی را cancel کنی؛ فعلاً فقط برمی‌گردونیم به انتخاب پلن
    await cq.message.edit_text(HEADER if SHOW_HEADER else INV, reply_markup=build_plans_kb())
    await cq.answer("پلن جدید را انتخاب کنید.")


# ===== انصراف از سفارش =====
@router.callback_query(F.data.startswith("cancel_order:"))
async def on_cancel_order(cq: types.CallbackQuery):
    order_id = cq.data.split(":", 1)[1]

    try:
        await update_order_status(order_id, "canceled", canceled_at=datetime.utcnow())
    except Exception:
        pass
    try:
        await expire_open_payments_for_order(order_id)
    except Exception:
        pass

    await cq.message.edit_text(
        rtl("❌ سفارش لغو شد. هر زمان خواستی می‌تونی از نو شروع کنی."),
        reply_markup=build_plans_kb()
    )
    await cq.answer("سفارش لغو شد.")


# ===== استیت‌های کارت‌به‌کارت =====
class C2C(StatesGroup):
    WaitingProof = State()


def rtl(s: str) -> str: return "\u200F" + s


def ltr(s: str) -> str: return "\u2066" + s + "\u2069"  # LTR isolate


def c2c_instruction_text(amount_toman: int, deadline_min: int) -> str:
    lines = [
        "💳 پرداخت کارت‌به‌کارت",
        "",
        f"• مبلغ: {fmt_price(amount_toman)}",
        f"• کارت: <code>{settings.C2C_CARD_NUMBER}</code>",  # ← LTR + قابل‌کپی
        f"• به‌نام: {settings.C2C_CARD_NAME}",
    ]
    if getattr(settings, "C2C_SHEBA", None):
        lines.append(f"• شبا: <code>{settings.C2C_SHEBA}</code>")
    lines += [
        "",
        "✅ لطفاً پس از واریز، رسید را به‌صورت عکس ارسال کنید.",
        f"⏳ مهلت ارسال رسید: {fa_num(str(deadline_min))} دقیقه",
        "",
        "ℹ️ اگر اشتباه شد، «برگشت به پرداخت» را بزنید."
    ]
    return rtl("\n".join(lines))


def build_c2c_back_kb(order_id: str, plan_key: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=rtl("⬅️ برگشت به پرداخت"), callback_data=f"after_order:{order_id}:{plan_key}")
    kb.adjust(1)
    return kb.as_markup()


# ===== آغاز کارت‌به‌کارت =====
@router.callback_query(F.data.startswith("pay_c2c:"))
async def start_c2c(cq: types.CallbackQuery, state: FSMContext):
    order_id = cq.data.split(":", 1)[1]
    order = await get_order(order_id)
    if not order:
        return await cq.answer("سفارش یافت نشد.", show_alert=True)

    plan_key = order["plan_code"]
    amount_toman = order["amount_toman"]

    due_at = datetime.utcnow() + timedelta(minutes=getattr(settings, "C2C_DEADLINE_MIN", 60))
    payment = await create_payment_request(order_id=order_id, method="c2c", due_at=due_at)

    await state.set_state(C2C.WaitingProof)
    await state.update_data(order_id=order_id, plan_key=plan_key, payment_id=str(payment["_id"]))

    await cq.message.edit_text(
        c2c_instruction_text(amount_toman, getattr(settings, "C2C_DEADLINE_MIN", 60)),
        reply_markup=build_c2c_back_kb(order_id, plan_key),
        parse_mode="HTML",
    )
    await cq.answer()


# ===== دریافت رسید (عکس/فایل/متن) =====
@router.message(C2C.WaitingProof, F.photo | F.document | F.text)
async def receive_c2c_proof(m: types.Message, state: FSMContext):
    data = await state.get_data()
    payment_id: str = data.get("payment_id")
    order_id: str = data.get("order_id")
    plan_key: str = data.get("plan_key")

    order = await get_order(order_id)
    if not order:
        await state.clear()
        return await m.answer(rtl("سفارش نامعتبر است."))

    proof_file_id = None
    proof_text = None
    proof_type = None

    if m.photo:
        proof_file_id = m.photo[-1].file_id
        proof_type = "photo"
    elif m.document:
        proof_file_id = m.document.file_id
        proof_type = "document"
    elif m.text:
        proof_text = m.text
        proof_type = "text"

    await attach_proof_to_payment(payment_id, proof_file_id, proof_text, proof_type=proof_type)
    await state.clear()

    admins = getattr(settings, "ADMIN_CHAT_IDS", [])
    if not admins:
        await m.answer(rtl("⚠️ رسید دریافت شد، اما ادمین تعریف نشده است. لطفاً با پشتیبانی تماس بگیرید."))
        return

    caption = (
            rtl("🧾 رسید جدید کارت‌به‌کارت ثبت شد") + "\n" +
            rtl(f"• سفارش: #{order_id[-6:]}") + "\n" +
            rtl(f"• مبلغ: {fmt_price(order['amount_toman'])}") + "\n" +
            rtl(f"• کاربر: @{m.from_user.username or 'بدون‌نام‌کاربری'} ({m.from_user.id})")
    )
    admin_kb = build_admin_decision_kb(payment_id)

    for admin_id in admins:
        try:
            if proof_file_id and m.photo:
                await m.bot.send_photo(admin_id, proof_file_id, caption=caption, reply_markup=admin_kb)
            elif proof_file_id and m.document:
                await m.bot.send_document(admin_id, proof_file_id, caption=caption, reply_markup=admin_kb)
            else:
                extra = ("\n" + rtl(f"متن: {proof_text[:400]}")) if proof_text else ""
                await m.bot.send_message(admin_id, caption + extra, reply_markup=admin_kb)
        except Exception:
            pass

    await m.answer(
        rtl("✅ رسید دریافت شد. پس از بررسی توسط پشتیبانی، اشتراک شما فعال می‌شود. برای تسریع، می‌توانید به پشتیبانی پیام دهید."),
        reply_markup=build_c2c_back_kb(order_id, plan_key)
    )


# ===== ادمین: تایید/رد =====
def is_admin(user_id: int) -> bool:
    return user_id in set(getattr(settings, "ADMIN_CHAT_IDS", []))


@router.callback_query(F.data.startswith("approve_payment:"))
async def on_approve_payment(cq: types.CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("اجازه دسترسی ندارید.", show_alert=True)

    payment_id = cq.data.split(":", 1)[1]
    ok = await approve_c2c_payment_and_mark_order_paid(payment_id, reviewer_uid=cq.from_user.id)

    if not ok:
        # تایید انجام نشد یا قبلاً رسیدگی شده
        return await cq.answer("پرداخت یافت نشد یا قبلاً رسیدگی شده.", show_alert=True)

    # --- Provision: بعد از تایید موفق پرداخت ---
    try:
        from services.provision import provision_paid_order
        from db.mongo_crud import get_payment_by_id  # اگر بالاتر ایمپورت نیست

        payment = await get_payment_by_id(payment_id)
        if payment:
            await provision_paid_order(payment["order_id"], cq.bot)
        else:
            await cq.message.answer(rtl("⚠️ پرداخت برای صدور سرویس پیدا نشد."))
    except Exception as e:
        # اگر خطا خورد، به ادمین اطلاع بده اما جریان اصلی ادامه داشته باشد
        try:
            await cq.message.answer(rtl(f"⚠️ خطا در صدور سرویس: {e}"))
        except Exception:
            pass

    await safe_edit(cq.message, caption=rtl("✅ پرداخت تایید شد و سفارش فعال گردید."))
    await cq.answer("پرداخت تایید شد.")

    # پیام به کاربر
    payment = await get_payment_by_id(payment_id)
    if payment:
        order = await get_order(payment["order_id"])
        if order:
            user = await get_user_by_id(order["user_id"])
            if user and user.get("tg_id") is not None:
                try:
                    await cq.bot.send_message(int(user["tg_id"]),
                                              rtl("🎉 پرداخت شما تایید شد و اشتراک فعال گردید. ممنون از خرید شما."))
                except Exception:
                    pass


@router.callback_query(F.data.startswith("reject_payment:"))
async def on_reject_payment(cq: types.CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("اجازه دسترسی ندارید.", show_alert=True)

    payment_id = cq.data.split(":", 1)[1]
    ok = await reject_c2c_payment(payment_id, reviewer_uid=cq.from_user.id, reason=None)
    if not ok:
        return await cq.answer("پرداخت یافت نشد یا قبلاً رسیدگی شده.", show_alert=True)

    await safe_edit(cq.message, caption=rtl("❌ پرداخت رد شد. لطفاً دوباره اقدام کنید یا با پشتیبانی در تماس باشید."))
    await cq.answer("پرداخت رد شد.")

    # پیام به کاربر
    payment = await get_payment_by_id(payment_id)
    if payment:
        order = await get_order(payment["order_id"])
        if order:
            user = await get_user_by_id(order["user_id"])
            if user and user.get("tg_id") is not None:
                try:
                    await cq.bot.send_message(int(user["tg_id"]),
                                              rtl("⚠️ پرداخت شما تایید نشد. لطفاً با پشتیبانی در تماس باشید یا مجدداً پرداخت کنید."))
                except Exception:
                    pass
