"""Builders for synthetic Telegram updates."""

from __future__ import annotations

from datetime import datetime

from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser

CUSTOMER_ID = 777001
ADMIN_ID = 999001


def tg_user(user_id: int) -> TgUser:
    return TgUser(id=user_id, is_bot=False, first_name="Tester", username=f"user{user_id}")


def message_update(text: str, user_id: int = CUSTOMER_ID, update_id: int = 1) -> Update:
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=tg_user(user_id),
            text=text,
        ),
    )


def callback_update(data: str, user_id: int = CUSTOMER_ID, update_id: int = 1) -> Update:
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=str(update_id),
            from_user=tg_user(user_id),
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=update_id,
                date=datetime.now(),
                chat=Chat(id=user_id, type="private"),
                from_user=tg_user(user_id),
                text="previous",
            ),
        ),
    )
