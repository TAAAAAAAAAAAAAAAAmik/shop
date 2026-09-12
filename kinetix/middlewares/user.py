"""Registers the user, resolves their locale, and blocks banned accounts."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from aiogram.types import User as TgUser

from kinetix.config import Settings
from kinetix.i18n import normalize_locale, t
from kinetix.services import users as user_service

log = logging.getLogger(__name__)


def _inner_event(event: TelegramObject) -> TelegramObject:
    """Unwrap an Update: this runs as an update-level outer middleware."""
    return event.event if isinstance(event, Update) else event


def _referrer_from_start(event: TelegramObject) -> int | None:
    """Read a `/start <id>` deep link, ignoring anything that isn't a user id."""
    event = _inner_event(event)
    if not isinstance(event, Message) or not event.text:
        return None
    parts = event.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[0].startswith("/start"):
        return None
    payload = parts[1].strip()
    return int(payload) if payload.isdigit() else None


class UserMiddleware(BaseMiddleware):
    """Reads :class:`Settings` from workflow data, like DbSessionMiddleware."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        settings: Settings = data["settings"]

        user, created = await user_service.get_or_create(
            data["session"],
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            locale=normalize_locale(tg_user.language_code or settings.default_locale),
            referrer_id=_referrer_from_start(event),
        )

        if user.is_banned:
            text = t(user.locale, "error.banned")
            inner = _inner_event(event)
            if isinstance(inner, CallbackQuery):
                await inner.answer(text, show_alert=True)
            elif isinstance(inner, Message):
                await inner.answer(text)
            return None

        data["user"] = user
        data["locale"] = user.locale
        data["is_new_user"] = created
        data["is_admin"] = settings.is_admin(user.id)
        return await handler(event, data)
