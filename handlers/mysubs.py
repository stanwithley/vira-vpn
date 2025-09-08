from aiogram import Router, types, F
router = Router()

@router.message(F.text == "📦 اشتراک‌های من")
async def my_subs_stub(m: types.Message):
    await m.answer("فعلاً اشتراکی نداری. بعد از خرید اینجا لیست می‌کنیم 📋")
