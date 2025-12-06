# main.py
import asyncio
import signal
import logging  # <--- اضافه شد
import sys

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

# تنظیمات لاگینگ (نمایش ساعت و سطح ارور)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

    # حذف وب‌هوک‌های قبلی
    await bot.delete_webhook(drop_pending_updates=True)

    # راه‌اندازی دیتابیس
    logger.info("⚙️ Initializing Database...")
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

    logger.info("🤖 Bot is running...")

    # === ارسال پیام به ادمین موقع روشن شدن ===
    try:
        # فرض بر اینه که توی config.py متغیر ADMIN_ID داری
        # اگر اسمش فرق داره، اینجا اصلاحش کن
        await bot.send_message(settings.ADMIN_ID, "✅ <b>Bot Started Successfully!</b>")
    except Exception as e:
        logger.error(f"Failed to send startup message to admin: {e}")
    # ========================================

    stop_event = asyncio.Event()

    def _stop(*_):
        logger.info("🛑 Stopping bot...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    try:
        await dp.start_polling(bot, allowed_updates=None)
    finally:
        logger.info("♻️ Cleaning up tasks...")
        for t in bg_tasks:
            t.cancel()
        await asyncio.gather(*bg_tasks, return_exceptions=True)
        await bot.session.close()
        logger.info("👋 Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually.")