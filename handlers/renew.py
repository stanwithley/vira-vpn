# handlers/renew.py
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.mongo_crud import get_or_create_user, get_plan_by_code
from db.mongo import subscriptions_col
from utils.locale import rtl, fa_num, fmt_dt

router = Router()

def quick_kb(plan_code: str | None):
    kb = InlineKeyboardBuilder()
    if plan_code:
        kb.button(text=rtl("🔁 تمدید همین پلن"), callback_data=f"renew:{plan_code}")
    kb.button(text=rtl("🛒 مشاهده پلن‌ها"), callback_data="renew:plans")
    kb.adjust(1)
    return kb.as_markup()

@router.message(F.text == "🔁 تمدید سرویس")
async def renew_handler(m: types.Message):
    user = await get_or_create_user(m.from_user.id, m.from_user.username, m.from_user.first_name)

    active = await subscriptions_col.find_one({"user_id": user["_id"], "status": "active"})
    if not active:
        return await m.answer(rtl(
            "در حال حاضر اشتراک فعالی ندارید.\nاز «🛒 خرید اشتراک» یک پلن انتخاب کنید."
        ))

    # اگر از پلن پولی بوده، همون کد رو پیشنهاد بده (trial رو پیشنهاد نده)
    plan_code = active["source_plan"] if active["source_plan"] != "trial" else None

    # نمایش خلاصه
    text = rtl(
        "🔁 تمدید سرویس:\n\n"
        f"• نوع: {active['source_plan']}\n"
        f"• ظرفیت: {fa_num(active.get('quota_mb', 0))} مگ\n"
        f"• دستگاه: {fa_num(active['devices'])}\n"
        f"• شروع: {fmt_dt(active['start_at'])}\n"
        f"• پایان: {fmt_dt(active['end_at'])}\n"
        "یکی از گزینه‌ها را انتخاب کنید:"
    )
    await m.answer(text, reply_markup=quick_kb(plan_code))

# اکشن‌های تمدید
@router.callback_query(F.data.startswith("renew:"))
async def renew_actions(cq: types.CallbackQuery):
    cmd = cq.data.split(":", 1)[1]
    if cmd == "plans":
        # ارجاع به لیست پلن‌ها (همون هندلر خریدت)
        await cq.message.edit_text(rtl("در حال انتقال به فهرست پلن‌ها…"))
        # بهتره پیام جدید با کیبورد خرید ارسال کنی: کار ساده:
        await cq.message.answer("🛒", reply_markup=None)  # placeholder
        from handlers.buy import build_plans_kb
        await cq.message.answer("\u2063", reply_markup=build_plans_kb())
        return await cq.answer()

    # تمدید همان پلن
    plan = await get_plan_by_code(cmd)
    if not plan:
        await cq.answer(rtl("پلن قابل تمدید یافت نشد."), show_alert=True)
        return
    # اینجا می‌تونی مستقیم سفارش تمدید بسازی یا ببری به فلو خرید همان پلن
    from handlers.buy import build_plan_actions_kb
    await cq.message.edit_text(
        rtl(f"تمدید پلن «{plan['title']}»"), reply_markup=build_plan_actions_kb(plan["code"])
    )
    await cq.answer()
