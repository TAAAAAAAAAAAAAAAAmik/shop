"""Reviewing manual bank transfers and editing the bank details."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.db.models import TopUp
from kinetix.i18n import t
from kinetix.keyboards import admin as kb
from kinetix.keyboards.callbacks import AdminCB, ReviewCB
from kinetix.money import format_money
from kinetix.services import payments, settings_store
from kinetix.services import topups as topup_service
from kinetix.states import AdminFlow
from kinetix.utils.tg import edit, escape

log = logging.getLogger(__name__)

router = Router(name="admin.requests")


def _card(topup: TopUp, locale: str, currency: str) -> str:
    submitted = topup.submitted_at or topup.created_at
    return t(
        locale,
        "admin.requests.card",
        reference=escape(topup.external_id),
        user=escape(topup.user.mention if topup.user else f"id{topup.user_id}"),
        user_id=topup.user_id,
        amount=format_money(topup.amount, currency),
        submitted=submitted.strftime("%d.%m.%Y %H:%M"),
    )


async def _notify_payer(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError as exc:
        log.warning("could not notify payer %s: %s", chat_id, exc)


@router.callback_query(AdminCB.filter(F.action == "requests"))
async def list_requests(
    callback: CallbackQuery,
    session: AsyncSession,
    locale: str,
    settings: Settings,
    state: FSMContext,
) -> None:
    await state.clear()
    queue = await topup_service.awaiting_review(session)
    if not queue:
        await edit(callback, t(locale, "admin.requests.empty"), kb.back(locale))
        return

    def label(topup: TopUp) -> str:
        return t(
            locale,
            "admin.requests.row",
            reference=topup.external_id,
            amount=format_money(topup.amount, settings.currency),
            user=topup.user.mention if topup.user else topup.user_id,
        )

    await edit(
        callback, t(locale, "admin.requests.title"), kb.requests_list(locale, queue, label)
    )


@router.callback_query(ReviewCB.filter(F.action == "open"))
async def open_request(
    callback: CallbackQuery,
    callback_data: ReviewCB,
    session: AsyncSession,
    locale: str,
    settings: Settings,
) -> None:
    topup = await session.get(TopUp, callback_data.topup_id)
    if topup is None or not topup.status.is_open:
        await edit(callback, t(locale, "admin.requests.gone"), kb.back(locale))
        return
    await edit(
        callback,
        _card(topup, locale, settings.currency),
        kb.review_actions(locale, topup.id),
    )


@router.callback_query(ReviewCB.filter(F.action == "approve"))
async def approve_request(
    callback: CallbackQuery,
    callback_data: ReviewCB,
    session: AsyncSession,
    locale: str,
    settings: Settings,
    dialect: str,
    bot: Bot,
) -> None:
    admin_id = callback.from_user.id
    credited = await topup_service.approve(
        session,
        callback_data.topup_id,
        admin_id=admin_id,
        dialect=dialect,
        referral_percent=settings.referral_percent,
    )
    if credited is None:
        # Already approved, rejected, or never claimed — whoever got here first won.
        await edit(callback, t(locale, "admin.requests.gone"), kb.back(locale))
        return

    topup = credited.topup
    payer = topup.user
    payer_locale = payer.locale if payer else "ru"

    await _notify_payer(
        bot,
        topup.user_id,
        t(
            payer_locale,
            "manual.approved",
            reference=escape(topup.external_id),
            amount=format_money(topup.amount, settings.currency),
            balance=format_money(credited.balance_after, settings.currency),
        ),
    )
    await payments.announce_referrer(bot, settings, credited)

    await edit(
        callback,
        t(
            locale,
            "admin.requests.approved",
            reference=escape(topup.external_id),
            user=escape(payer.mention if payer else f"id{topup.user_id}"),
            balance=format_money(credited.balance_after, settings.currency),
        ),
        kb.back(locale),
    )


@router.callback_query(ReviewCB.filter(F.action == "reject"))
async def reject_request(
    callback: CallbackQuery,
    callback_data: ReviewCB,
    session: AsyncSession,
    locale: str,
    settings: Settings,
    bot: Bot,
) -> None:
    rejected = await topup_service.reject(
        session, callback_data.topup_id, admin_id=callback.from_user.id
    )
    if rejected is None:
        await edit(callback, t(locale, "admin.requests.gone"), kb.back(locale))
        return

    payer = rejected.user
    support = f"@{settings.support_username}" if settings.support_username else "—"
    await _notify_payer(
        bot,
        rejected.user_id,
        t(
            payer.locale if payer else "ru",
            "manual.rejected",
            reference=escape(rejected.external_id),
            amount=format_money(rejected.amount, settings.currency),
            support=escape(support),
        ),
    )
    await edit(
        callback,
        t(locale, "admin.requests.rejected", reference=escape(rejected.external_id)),
        kb.back(locale),
    )


# --- bank details -----------------------------------------------------------


@router.callback_query(AdminCB.filter(F.action == "requisites"))
async def show_requisites(
    callback: CallbackQuery,
    session: AsyncSession,
    locale: str,
    settings: Settings,
    state: FSMContext,
) -> None:
    await state.set_state(AdminFlow.requisites)
    current = await settings_store.requisites(session, settings.manual_requisites)
    text = (
        t(locale, "admin.requisites.current", requisites=escape(current))
        if current
        else t(locale, "admin.requisites.empty")
    )
    await edit(callback, text, kb.back(locale))


@router.message(AdminFlow.requisites, F.text)
async def save_requisites(
    message: Message, session: AsyncSession, locale: str, state: FSMContext
) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer(t(locale, "admin.requisites.empty"))
        return

    await settings_store.set_value(session, settings_store.MANUAL_REQUISITES, value)
    await state.clear()
    await message.answer(t(locale, "admin.requisites.saved"), reply_markup=kb.back(locale))
