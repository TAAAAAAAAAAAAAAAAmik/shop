"""A Bot whose session records outgoing calls instead of hitting Telegram."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import TelegramMethod
from aiogram.types import Chat, Message
from aiogram.types import User as TgUser

BOT_ID = 424242
BOT_USERNAME = "kinetix_test_bot"


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []

    def named(self, name: str) -> list[TelegramMethod[Any]]:
        return [c for c in self.calls if type(c).__name__ == name]

    def texts(self) -> list[str]:
        return [
            getattr(call, "text", "") or getattr(call, "caption", "") or ""
            for call in self.calls
        ]

    @property
    def last_text(self) -> str:
        texts = [text for text in self.texts() if text]
        return texts[-1] if texts else ""

    async def close(self) -> None:  # pragma: no cover - nothing to close
        pass

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield b""

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109 - signature fixed by BaseSession
    ) -> Any:
        self.calls.append(method)
        name = type(method).__name__

        if name == "GetMe":
            return TgUser(
                id=BOT_ID, is_bot=True, first_name="Kinetix", username=BOT_USERNAME
            )
        if name in {"SendMessage", "EditMessageText", "SendDocument"}:
            chat_id = getattr(method, "chat_id", 1)
            return Message(
                message_id=len(self.calls),
                date=datetime.now(),
                chat=Chat(id=int(chat_id) if chat_id else 1, type="private"),
                text=getattr(method, "text", None),
            )
        return True


def make_bot() -> tuple[Bot, RecordingSession]:
    session = RecordingSession()
    bot = Bot(
        token=f"{BOT_ID}:TEST-TOKEN-FOR-UNIT-TESTS",
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    return bot, session
