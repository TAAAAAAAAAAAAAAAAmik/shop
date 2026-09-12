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
from kinetix.keyboards import admin as admin_kb
from kinetix.keyboards import user as kb
from kinetix.keyboards.callbacks import MenuCB, PayCB, TopUpCB
from kinetix.money import MoneyError, format_money, parse_amount
from kinetix.services import notify, payments, settings_store
from kinetix.services import topups as topup_service
from kinetix.services.cryptobot import CryptoPay
from kinetix.states import TopUpFlow
from kinetix.utils.tg import edit, escape

log = logging.getLogger(__name__)

router = Router(name="balance")


def _support(settings: Settings) -> str:
    return f"@{settings.support_username}" if settings.support_username else "—"


async def _manual_available(session: AsyncSession, settings: Settings) -> bool:
    if not settings.manual_payment_enabled:
        return False
    return bool(await settings_store.requisites(session, settings.manual_requisites))


@router.callback_query(MenuCB.filter(F.action == "topup"))
async def open_topup(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
    crypto: CryptoPay | None,
) -> None:
    await state.clear()
    manual = await _manual_available(session, settings)

    if crypto is None and not manual:
        await edit(
            callback,
            t(user.locale, "balance.no_methods", support=escape(_support(settings))),
            kb.back_to(user.locale),
        )
        return

    await edit(
        callback,
        t(
            user.locale,
            "balance.method",
            balance=format_money(user.balance, settings.currency),
        ),
        kb.topup_methods(user.locale, crypto=crypto is not None, manual=manual),
    )


@router.callback_query(PayCB.filter(F.method == "crypto"))
async def open_crypto_topup(
    callback: CallbackQuery,
    user: User,
    settings: Settings,
    state: FSMContext,
    crypto: CryptoPay | None,
) -> None:
    if crypto is None:
        await edit(
            callback,
            t(user.locale, "balance.disabled", support=escape(_support(settings))),
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


# --- manual bank transfer ---------------------------------------------------


def _amount_in_range(amount: int, settings: Settings) -> bool:
    return settings.min_topup <= amount <= settings.max_topup


async def _show_request(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    settings: Settings,
    topup: TopUp,
) -> None:
    """Render an existing request in whatever state it is in."""
    if topup.status is TopUpStatus.AWAITING_REVIEW:
        await edit(
            callback,
            t(
                user.locale,
                "manual.claimed",
                reference=escape(topup.external_id),
                amount=format_money(topup.amount, settings.currency),
            ),
            kb.manual_request(user.locale, topup.id, claimable=False),
        )
        return

    details = await settings_store.requisites(session, settings.manual_requisites)
    await edit(
        callback,
        t(
            user.locale,
            "manual.instructions",
            amount=format_money(topup.amount, settings.currency),
            requisites=escape(details),
            reference=escape(topup.external_id),
            ttl=settings.manual_ttl_minutes,
        ),
        kb.manual_request(user.locale, topup.id, claimable=True),
    )


@router.callback_query(PayCB.filter(F.method == "manual"))
async def open_manual_topup(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _manual_available(session, settings):
        await edit(
            callback,
            t(user.locale, "manual.unavailable", support=escape(_support(settings))),
            kb.back_to(user.locale),
        )
        return

    # One open request at a time, otherwise staff cannot tell the transfers apart.
    existing = await topup_service.open_manual(session, user.id)
    if existing is not None:
        await state.clear()
        await _show_request(callback, session, user, settings, existing)
        return

    await state.set_state(TopUpFlow.manual_amount)
    await edit(
        callback,
        t(
            user.locale,
            "manual.ask_amount",
            min=format_money(settings.min_topup, settings.currency),
            max=format_money(settings.max_topup, settings.currency),
        ),
        kb.back_to(user.locale),
    )


@router.message(TopUpFlow.manual_amount, F.text)
async def create_manual_request(
    message: Message,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
) -> None:
    try:
        amount = parse_amount(message.text or "")
    except MoneyError:
        await message.answer(t(user.locale, "balance.bad_amount"))
        return

    if not _amount_in_range(amount, settings):
        await message.answer(
            t(
                user.locale,
                "balance.out_of_range",
                min=format_money(settings.min_topup, settings.currency),
                max=format_money(settings.max_topup, settings.currency),
            )
        )
        return

    existing = await topup_service.open_manual(session, user.id)
    if existing is not None:
        await state.clear()
        await message.answer(
            t(
                user.locale,
                "manual.already_open",
                reference=escape(existing.external_id),
                amount=format_money(existing.amount, settings.currency),
            )
        )
        return

    topup = await topup_service.create_manual(
        session, user_id=user.id, amount=amount, ttl_minutes=settings.manual_ttl_minutes
    )
    details = await settings_store.requisites(session, settings.manual_requisites)
    await state.clear()
    await message.answer(
        t(
            user.locale,
            "manual.instructions",
            amount=format_money(amount, settings.currency),
            requisites=escape(details),
            reference=escape(topup.external_id),
            ttl=settings.manual_ttl_minutes,
        ),
        reply_markup=kb.manual_request(user.locale, topup.id, claimable=True),
    )


@router.callback_query(TopUpCB.filter(F.action == "paid"))
async def claim_paid(
    callback: CallbackQuery,
    callback_data: TopUpCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
    bot: Bot,
) -> None:
    topup = await session.get(TopUp, callback_data.topup_id)
    if topup is None or topup.user_id != user.id:
        await callback.answer(t(user.locale, "error.stale"), show_alert=True)
        return

    if topup.status is TopUpStatus.AWAITING_REVIEW:
        await callback.answer(
            t(user.locale, "manual.under_review", reference=topup.external_id), show_alert=True
        )
        return

    submitted = await topup_service.submit_for_review(session, topup.id)
    if submitted is None:
        await callback.answer(t(user.locale, "error.stale"), show_alert=True)
        return

    await edit(
        callback,
        t(
            user.locale,
            "manual.claimed",
            reference=escape(submitted.external_id),
            amount=format_money(submitted.amount, settings.currency),
        ),
        kb.manual_request(user.locale, submitted.id, claimable=False),
    )

    await notify.admins(
        bot,
        settings.admin_ids,
        t(
            "ru",
            "admin.notify.review",
            reference=escape(submitted.external_id),
            user=escape(user.mention),
            user_id=user.id,
            amount=format_money(submitted.amount, settings.currency),
        ),
        reply_markup=admin_kb.review_actions("ru", submitted.id),
    )


@router.callback_query(TopUpCB.filter(F.action == "cancel"))
async def cancel_request(
    callback: CallbackQuery,
    callback_data: TopUpCB,
    session: AsyncSession,
    user: User,
) -> None:
    cancelled = await topup_service.cancel(session, callback_data.topup_id, user.id)
    if not cancelled:
        await callback.answer(t(user.locale, "error.stale"), show_alert=True)
        return
    await edit(callback, t(user.locale, "manual.cancelled"), kb.back_to(user.locale))
