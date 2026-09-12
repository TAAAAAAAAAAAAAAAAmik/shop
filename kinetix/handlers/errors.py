"""Last line of defence: log the traceback, show the user something human."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ErrorEvent, Message

from kinetix.errors import ShopError
from kinetix.i18n import t

log = logging.getLogger(__name__)

router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    update = event.update
    locale = "ru"
    target: Message | CallbackQuery | None = None

    if update.message is not None:
        target = update.message
        locale = update.message.from_user.language_code if update.message.from_user else "ru"
    elif update.callback_query is not None:
        target = update.callback_query
        locale = (
            update.callback_query.from_user.language_code
            if update.callback_query.from_user
            else "ru"
        )

    locale = "en" if (locale or "").startswith("en") else "ru"

    if isinstance(event.exception, ShopError):
        log.info("handled shop error: %s", event.exception)
    else:
        log.exception("unhandled error in update %s", update.update_id, exc_info=event.exception)

    try:
        if isinstance(target, CallbackQuery):
            await target.answer(t(locale, "error.generic"), show_alert=True)
        elif isinstance(target, Message):
            await target.answer(t(locale, "error.generic"))
    except TelegramAPIError:
        pass  # the user may have blocked the bot mid-update

    return True
