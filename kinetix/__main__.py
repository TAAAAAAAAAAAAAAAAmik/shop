"""Kinetix entry point: wire everything together and start polling."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from kinetix.config import Settings, get_settings
from kinetix.db.base import Database
from kinetix.handlers import admin, balance, catalog, common, errors
from kinetix.logger import configure as configure_logging
from kinetix.middlewares.db import DbSessionMiddleware
from kinetix.middlewares.throttling import ThrottlingMiddleware
from kinetix.middlewares.user import UserMiddleware
from kinetix.services.cryptobot import CryptoPay
from kinetix.services.payments import PaymentPoller

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Меню / Menu"),
    BotCommand(command="menu", description="Меню / Menu"),
    BotCommand(command="cancel", description="Отмена / Cancel"),
]


def build_dispatcher(db: Database, settings: Settings, crypto: CryptoPay | None) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Outer middlewares run for every update, in registration order.
    dp.update.outer_middleware(ThrottlingMiddleware(settings.throttle_rate))
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserMiddleware())

    dp.include_routers(
        common.router,
        catalog.router,
        balance.router,
        admin.build_router(),
        errors.router,
    )

    dp["database"] = db
    dp["settings"] = settings
    dp["crypto"] = crypto
    return dp


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    db = Database(settings.database_url)
    await db.create_all()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    crypto = (
        CryptoPay(settings.crypto_pay_token, testnet=settings.crypto_pay_testnet)
        if settings.crypto_pay_enabled
        else None
    )

    dp = build_dispatcher(db, settings, crypto)

    me = await bot.get_me()
    dp["bot_username"] = me.username
    log.info("starting %s as @%s (db: %s)", settings.shop_name, me.username, db.dialect)
    if crypto is None:
        log.warning("CRYPTO_PAY_TOKEN is not set — top-ups are disabled")

    poller = None
    if crypto is not None:
        poller = PaymentPoller(db, crypto, bot, settings)
        poller.start()

    await bot.set_my_commands(COMMANDS)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if poller is not None:
            await poller.stop()
        if crypto is not None:
            await crypto.close()
        await bot.session.close()
        await db.dispose()
        log.info("stopped")


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    run()
