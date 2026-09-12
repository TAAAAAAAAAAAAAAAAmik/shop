"""Balance adjustments, promo creation and broadcasts."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.db.base import Database
from kinetix.db.models import PromoCode, TxKind
from kinetix.errors import InsufficientFunds
from kinetix.i18n import t
from kinetix.keyboards import admin as kb
from kinetix.keyboards.callbacks import AdminCB
from kinetix.money import MoneyError, format_money, parse_amount
from kinetix.services import promo as promo_service
from kinetix.services import users as user_service
from kinetix.services import wallet
from kinetix.states import AdminFlow
from kinetix.utils.tg import edit, escape

log = logging.getLogger(__name__)

router = Router(name="admin.ops")

BROADCAST_DELAY = 0.05  # ~20 messages/sec, Telegram's documented ceiling


# --- balance ----------------------------------------------------------------


@router.callback_query(AdminCB.filter(F.action == "balance"))
async def ask_user(callback: CallbackQuery, locale: str, state: FSMContext) -> None:
    await state.set_state(AdminFlow.balance_user)
    await edit(callback, t(locale, "admin.balance.ask_user"), kb.back(locale))


@router.message(AdminFlow.balance_user, F.text)
async def receive_user(
    message: Message, session: AsyncSession, locale: str, settings: Settings, state: FSMContext
) -> None:
    target = await user_service.find(session, message.text or "")
    if target is None:
        await message.answer(t(locale, "admin.balance.no_user"))
        return

    await state.set_state(AdminFlow.balance_amount)
    await state.update_data(target_id=target.id)
    await message.answer(
        t(
            locale,
            "admin.balance.ask_amount",
            user=escape(target.mention),
            balance=format_money(target.balance, settings.currency),
        )
    )


@router.message(AdminFlow.balance_amount, F.text)
async def receive_amount(
    message: Message,
    session: AsyncSession,
    locale: str,
    settings: Settings,
    state: FSMContext,
) -> None:
    try:
        amount = parse_amount(message.text or "")
    except MoneyError:
        await message.answer(t(locale, "balance.bad_amount"))
        return

    data = await state.get_data()
    target = await user_service.find(session, str(data.get("target_id", "")))
    if target is None:
        await state.clear()
        await message.answer(t(locale, "admin.balance.no_user"))
        return

    try:
        await wallet.apply_tx(
            session,
            target,
            amount,
            TxKind.ADMIN,
            ref_id=message.from_user.id if message.from_user else None,
            comment="manual adjustment",
        )
        await session.commit()
    except InsufficientFunds as exc:
        await session.rollback()
        await message.answer(
            t(
                locale,
                "admin.balance.negative",
                missing=format_money(exc.missing, settings.currency),
            )
        )
        return

    await state.clear()
    await message.answer(
        t(
            locale,
            "admin.balance.done",
            user=escape(target.mention),
            balance=format_money(target.balance, settings.currency),
        ),
        reply_markup=kb.back(locale),
    )


# --- promo ------------------------------------------------------------------


@router.callback_query(AdminCB.filter(F.action == "promo"))
async def ask_promo(callback: CallbackQuery, locale: str, state: FSMContext) -> None:
    await state.set_state(AdminFlow.promo_spec)
    await edit(callback, t(locale, "admin.promo.ask"), kb.back(locale))


@router.message(AdminFlow.promo_spec, F.text)
async def create_promo(
    message: Message, session: AsyncSession, locale: str, state: FSMContext
) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(t(locale, "admin.promo.bad"))
        return

    code = promo_service.normalize(parts[0])
    try:
        percent = int(parts[1])
        max_uses = int(parts[2]) if len(parts) > 2 else 0
        per_user = int(parts[3]) if len(parts) > 3 else 1
    except ValueError:
        await message.answer(t(locale, "admin.promo.bad"))
        return

    if not code or not 1 <= percent <= 100 or max_uses < 0 or per_user < 0:
        await message.answer(t(locale, "admin.promo.bad"))
        return

    existing = (
        await session.execute(select(PromoCode).where(PromoCode.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        # Re-issuing a code updates it rather than failing on the unique index.
        existing.percent = percent
        existing.max_uses = max_uses
        existing.per_user_limit = per_user
        existing.is_active = True
    else:
        session.add(
            PromoCode(code=code, percent=percent, max_uses=max_uses, per_user_limit=per_user)
        )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await message.answer(t(locale, "admin.promo.bad"))
        return

    await state.clear()
    await message.answer(
        t(locale, "admin.promo.done", code=escape(code), percent=percent),
        reply_markup=kb.back(locale),
    )


# --- broadcast --------------------------------------------------------------


@router.callback_query(AdminCB.filter(F.action == "broadcast"))
async def ask_broadcast(callback: CallbackQuery, locale: str, state: FSMContext) -> None:
    await state.set_state(AdminFlow.broadcast_message)
    await edit(callback, t(locale, "admin.broadcast.ask"), kb.back(locale))


@router.message(AdminFlow.broadcast_message)
async def start_broadcast(
    message: Message,
    session: AsyncSession,
    locale: str,
    state: FSMContext,
    db: Database,
    bot: Bot,
) -> None:
    recipients = await user_service.all_user_ids(session)
    await state.clear()
    await message.answer(
        t(locale, "admin.broadcast.started", count=len(recipients)),
        reply_markup=kb.back(locale),
    )
    asyncio.create_task(  # noqa: RUF006 - long-running, reports back when finished
        _run_broadcast(bot, message, recipients, locale)
    )


async def _run_broadcast(
    bot: Bot, source: Message, recipients: list[int], locale: str
) -> None:
    sent = failed = 0
    for chat_id in recipients:
        try:
            await source.send_copy(chat_id)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await source.send_copy(chat_id)
                sent += 1
            except TelegramAPIError:
                failed += 1
        except TelegramAPIError:
            failed += 1  # blocked the bot, deleted account, etc.
        await asyncio.sleep(BROADCAST_DELAY)

    if source.from_user is not None:
        try:
            await bot.send_message(
                source.from_user.id,
                t(locale, "admin.broadcast.done", sent=sent, failed=failed),
            )
        except TelegramAPIError:
            log.info("broadcast finished: sent=%s failed=%s", sent, failed)
