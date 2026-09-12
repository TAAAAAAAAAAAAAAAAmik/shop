"""Per-user rate limiting, so a held-down button can't hammer the database."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

PRUNE_EVERY = 500


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 0.4) -> None:
        self.rate = rate
        self._seen: dict[int, float] = {}
        self._calls = 0

    def _prune(self, now: float) -> None:
        self._calls += 1
        if self._calls % PRUNE_EVERY:
            return
        cutoff = now - max(self.rate * 10, 60)
        self._seen = {uid: ts for uid, ts in self._seen.items() if ts > cutoff}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        now = time.monotonic()
        self._prune(now)
        last = self._seen.get(tg_user.id, 0.0)
        if now - last < self.rate:
            if isinstance(event, CallbackQuery):
                await event.answer()  # silently ack so the spinner stops
            return None

        self._seen[tg_user.id] = now
        return await handler(event, data)
