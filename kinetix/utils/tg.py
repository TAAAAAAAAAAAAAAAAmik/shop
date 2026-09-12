"""Telegram helpers that smooth over the API's rough edges."""

from __future__ import annotations

import html
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup

log = logging.getLogger(__name__)

# Telegram rejects messages over 4096 chars; leave room for the wrapper text.
MAX_TEXT = 3500


async def edit(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit the callback's message, tolerating the 'not modified' no-op."""
    if callback.message is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            pass
        elif "message can't be edited" in str(exc) or "message to edit not found" in str(exc):
            await callback.message.answer(text, reply_markup=reply_markup)
        else:
            raise
    await callback.answer()


def escape(value: object) -> str:
    return html.escape(str(value), quote=False)


def goods_document(payloads: list[str], order_id: int) -> BufferedInputFile:
    body = "\n".join(payloads).encode("utf-8")
    return BufferedInputFile(body, filename=f"order-{order_id}.txt")


def fits_in_message(payloads: list[str]) -> bool:
    return sum(len(p) + 1 for p in payloads) <= MAX_TEXT
