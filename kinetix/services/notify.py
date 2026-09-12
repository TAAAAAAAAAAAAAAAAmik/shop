"""Fire-and-forget notifications to shop staff."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup

log = logging.getLogger(__name__)


async def admins(
    bot: Bot,
    admin_ids: list[int],
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Tell every admin something. Never raises into the calling handler."""
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except TelegramAPIError as exc:
            log.warning("could not notify admin %s: %s", admin_id, exc)
        await asyncio.sleep(0.05)
