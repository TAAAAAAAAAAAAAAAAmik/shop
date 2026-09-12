"""Topping the wallet up through CryptoBot."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.db.models import TopUp, TopUpStatus, User
from kinetix.errors import PaymentError
from kinetix.i18n import t
from kinetix.keyboards import user as kb
from kinetix.keyboards.callbacks import MenuCB, TopUpCB
from kinetix.money import MoneyError, format_money, parse_amount
from kinetix.services import notify, payments
from kinetix.services import topups as topup_service
from kinetix.services.cryptobot import CryptoPay
from kinetix.states import TopUpFlow
from kinetix.utils.tg import edit, escape

log = logging.getLogger(__name__)

router = Router(name="balance")


@router.callback_query(MenuCB.filter(F.action == "topup"))
async def open_topup(
    callback: CallbackQuery,
    user: User,
    settings: Settings,
    state: FSMContext,
    crypto: CryptoPay | None,
) -> None:
    if crypto is None:
        support = f"@{settings.support_username}" if settings.support_username else "—"
        await edit(
            callback,
            t(user.locale, "balance.disabled", support=escape(support)),
            kb.back_to(user.locale),
        )
        return

    await state.set_state(TopUpFlow.amount)
    await edit(
        callback,
        t(
            user.locale,
            "balance.title",
            balance=format_money(user.balance, settings.currency),
            min=format_money(settings.min_topup, settings.currency),
            max=format_money(settings.max_topup, settings.currency),
        ),
        kb.back_to(user.locale),
    )


@router.message(TopUpFlow.amount, F.text)
async def create_invoice(
    message: Message,
    user: User,
    settings: Settings,
    session: AsyncSession,
    state: FSMContext,
    crypto: CryptoPay | None,
) -> None:
    if crypto is None:
        await state.clear()
        return

    try:
        amount = parse_amount(message.text or "")
    except MoneyError:
        await message.answer(t(user.locale, "balance.bad_amount"))
        return

    if not settings.min_topup <= amount <= settings.max_topup:
        await message.answer(
            t(
                user.locale,
                "balance.out_of_range",
                min=format_money(settings.min_topup, settings.currency),
                max=format_money(settings.max_topup, settings.currency),
            )
        )
        return

    try:
        invoice = await crypto.create_invoice(
            amount_minor=amount,
            fiat=settings.currency,
            description=f"{settings.shop_name}: balance top-up",
            payload=str(user.id),
            expires_in=settings.invoice_ttl_minutes * 60,
        )
    except PaymentError as exc:
        log.warning("invoice creation failed for %s: %s", user.id, exc)
        await message.answer(t(user.locale, "error.generic"))
        return

    topup = await topup_service.create(
        session,
        user_id=user.id,
        provider=payments.PROVIDER,
        external_id=invoice.invoice_id,
        amount=amount,
        pay_url=invoice.pay_url,
        ttl_minutes=settings.invoice_ttl_minutes,
    )
    await state.clear()
    await message.answer(
        t(
            user.locale,
            "balance.invoice",
            amount=format_money(amount, settings.currency),
            ttl=settings.invoice_ttl_minutes,
        ),
        reply_markup=kb.invoice(user.locale, topup.id, invoice.pay_url),
    )


@router.callback_query(TopUpCB.filter(F.action == "check"))
async def check_invoice(
    callback: CallbackQuery,
    callback_data: TopUpCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
    dialect: str,
    crypto: CryptoPay | None,
    bot: Bot,
) -> None:
    topup = await session.get(TopUp, callback_data.topup_id)
    if topup is None or topup.user_id != user.id or crypto is None:
        await callback.answer(t(user.locale, "error.stale"), show_alert=True)
        return

    if topup.status is TopUpStatus.PAID:
        # Already settled by the poller — just show the current state.
        await edit(
            callback,
            t(
                user.locale,
                "balance.credited",
                amount=format_money(topup.amount, settings.currency),
                balance=format_money(user.balance, settings.currency),
            ),
            kb.back_to(user.locale),
        )
        return

    try:
        credited = await payments.settle(session, crypto, topup, settings, dialect)
    except PaymentError as exc:
        log.warning("manual invoice check failed: %s", exc)
        await callback.answer(t(user.locale, "error.generic"), show_alert=True)
        return

    if credited is None:
        await callback.answer(t(user.locale, "balance.still_pending"), show_alert=True)
        return

    await edit(
        callback,
        t(
            user.locale,
            "balance.credited",
            amount=format_money(credited.topup.amount, settings.currency),
            balance=format_money(credited.balance_after, settings.currency),
        ),
        kb.back_to(user.locale),
    )
    await payments.announce_referrer(bot, settings, credited)
    await notify.admins(
        bot,
        settings.admin_ids,
        t(
            "ru",
            "admin.notify.topup",
            user=escape(user.mention),
            amount=format_money(credited.topup.amount, settings.currency),
        ),
    )
