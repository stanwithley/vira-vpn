from aiogram import Router, types, F
router = Router()

@router.message(F.text == "👛 کیف پول / شارژ")
async def wallet_stub(m: types.Message):
    await m.answer("کیف پول: موجودی 0 تومان.\nبه‌زودی «شارژ کیف پول» اضافه میشه 💳")
