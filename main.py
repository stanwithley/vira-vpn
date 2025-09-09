# main.py
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from handlers import admin_manage
from config import settings
from db.mongo import ensure_indexes
from db.mongo_crud import ensure_default_plans
from db.schema import ensure_collections_and_validators
from handlers import start, trial, buy, renew, wallet, mysubs, help as help_h, support


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    await ensure_collections_and_validators()
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


    # DB bootstrapping
    await ensure_indexes()
    await ensure_default_plans()

    print("🤖 Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
