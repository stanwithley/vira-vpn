from aiogram import Router, types
router = Router()

@router.message()
async def see_all(m: types.Message):
    text = m.text or m.caption or "<no text>"
    await m.answer(f"🧪 DEBUG\n"
                   f"type={m.content_type}\n"
                   f"text={text!r}")
