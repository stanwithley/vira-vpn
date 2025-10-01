# main.py
import asyncio
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import settings
from db.mongo import ensure_indexes
from db.mongo_crud import ensure_default_plans
from db.schema import ensure_collections_and_validators
from handlers import admin_manage, debug
from handlers import start, trial, buy, renew, wallet, mysubs, help as help_h, support
from services.enforcer import expire_loop
from services.quota_enforcer import quota_loop


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    # اگر قبلاً وبهوک بوده، قطعش کن و پیام‌های معوقه رو نادیده بگیر
    await bot.delete_webhook(drop_pending_updates=True)

    # دیتابیس و اسکیمای اولیه
    await ensure_collections_and_validators()
    await ensure_indexes()
    await ensure_default_plans()

    dp = Dispatcher()

    # Routers
    dp.include_router(start.router)
    dp.include_router(trial.router)
    dp.include_router(buy.router)
    dp.include_router(renew.router)
    dp.include_router(wallet.router)
    dp.include_router(mysubs.router)
    dp.include_router(help_h.router)
    dp.include_router(support.router)
    dp.include_router(admin_manage.router)
    dp.include_router(debug.router)

    # تسک‌های پس‌زمینه
    bg_tasks = [
        asyncio.create_task(expire_loop(), name="expire_loop"),
        asyncio.create_task(quota_loop(bot), name="quota_loop"),
    ]

    print("🤖 Bot is running...")

    # هندل سیگنال برای توقف تمیز
    stop_event = asyncio.Event()

    def _stop(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            # روی ویندوز ممکنه در دسترس نباشه
            pass

    # polling
    try:
        await dp.start_polling(bot, allowed_updates=None)
    finally:
        # توقف تمیز تسک‌ها
        for t in bg_tasks:
            t.cancel()
        await asyncio.gather(*bg_tasks, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
