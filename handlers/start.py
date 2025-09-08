# handlers/start.py
from aiogram import Router, types, F
from db.mongo_crud import get_or_create_user
from keyboards.main_menu import main_menu   # ⬅️ اینو اضافه کن

router = Router()

@router.message(F.text == "/start")
async def start_cmd(m: types.Message):
    # ثبت/آپدیت کاربر در MongoDB
    await get_or_create_user(
        tg_id=m.from_user.id,
        username=m.from_user.username,
        first_name=m.from_user.first_name,
    )

    # پیام خوش‌آمد + منوی اصلی
    await m.answer(
        "سلام! خوش اومدی 👋\n"
        "از منوی زیر می‌تونی اکانت تست بگیری یا پلن خریداری کنی:",
        reply_markup=main_menu()
    )
