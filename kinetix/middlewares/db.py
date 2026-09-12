"""Hands every handler its own session, closed when the update is done.

The :class:`Database` is read from the dispatcher's workflow data
(``dp["database"]``) rather than captured at construction time, so the same
dispatcher can be pointed at a different database — which is what the
integration tests do.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from kinetix.db.base import Database


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        db: Database = data["database"]
        async with db.session() as session:
            data["session"] = session
            data["db"] = db
            data["dialect"] = db.dialect
            return await handler(event, data)
