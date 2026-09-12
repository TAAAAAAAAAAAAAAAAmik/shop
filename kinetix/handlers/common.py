"""Entry point, main menu and the simple informational screens."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.db.models import User
from kinetix.i18n import t
from kinetix.keyboards import user as kb
from kinetix.keyboards.callbacks import LangCB, MenuCB
from kinetix.money import format_money
from kinetix.services import orders as order_service
from kinetix.services import users as user_service
from kinetix.services import wallet
from kinetix.utils.tg import edit, escape

router = Router(name="common")


def menu_text(user: User, settings: Settings) -> str:
    return t(
        user.locale,
        "menu.title",
        shop=escape(settings.shop_name),
        balance=format_money(user.balance, settings.currency),
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User,
    settings: Settings,
    is_admin: bool,
    is_new_user: bool,
) -> None:
    await state.clear()
    greeting = t(user.locale, "start.welcome", shop=escape(settings.shop_name))
    if is_new_user and user.referrer_id:
        greeting += "\n" + t(user.locale, "start.referred")
    await message.answer(greeting)
    await message.answer(
        menu_text(user, settings), reply_markup=kb.main_menu(user.locale, is_admin=is_admin)
    )


@router.message(Command("menu"))
async def cmd_menu(
    message: Message, state: FSMContext, user: User, settings: Settings, is_admin: bool
) -> None:
    await state.clear()
    await message.answer(
        menu_text(user, settings), reply_markup=kb.main_menu(user.locale, is_admin=is_admin)
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, locale: str) -> None:
    await state.clear()
    await message.answer(t(locale, "cancelled"))


@router.callback_query(MenuCB.filter(F.action == "home"))
async def open_menu(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    settings: Settings,
    is_admin: bool,
) -> None:
    await state.clear()
    await edit(
        callback, menu_text(user, settings), kb.main_menu(user.locale, is_admin=is_admin)
    )


@router.callback_query(MenuCB.filter(F.action == "profile"))
async def open_profile(
    callback: CallbackQuery, session: AsyncSession, user: User, settings: Settings
) -> None:
    recent = await wallet.history(session, user.id, limit=5)
    orders = await order_service.user_orders(session, user.id, limit=100)
    referrals = await user_service.referral_count(session, user.id)

    text = t(
        user.locale,
        "profile.card",
        id=user.id,
        balance=format_money(user.balance, settings.currency),
        orders=len(orders),
        spent=format_money(user.total_spent, settings.currency),
        referrals=referrals,
    )
    if recent:
        rows = "\n".join(
            t(
                user.locale,
                "profile.history_row",
                sign="+" if tx.amount >= 0 else "−",
                amount=format_money(abs(tx.amount), settings.currency),
                kind=tx.kind.value,
            )
            for tx in recent
        )
        text += t(user.locale, "profile.history", rows=rows)

    await edit(callback, text, kb.back_to(user.locale))


@router.callback_query(MenuCB.filter(F.action == "orders"))
async def open_orders(
    callback: CallbackQuery, session: AsyncSession, user: User, settings: Settings
) -> None:
    history = await order_service.user_orders(session, user.id, limit=10)
    text = t(user.locale, "orders.title")
    if not history:
        text += "\n\n" + t(user.locale, "orders.empty")
    else:
        rows = "\n".join(
            t(
                user.locale,
                "orders.row",
                order_id=order.id,
                title=escape(order.product.title(user.locale)),
                quantity=order.quantity,
                total=format_money(order.total, settings.currency),
                date=order.created_at.strftime("%d.%m.%Y"),
            )
            for order in history
        )
        text += "\n\n" + rows
    await edit(callback, text, kb.back_to(user.locale))


@router.callback_query(MenuCB.filter(F.action == "referral"))
async def open_referral(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    settings: Settings,
    bot_username: str,
) -> None:
    count = await user_service.referral_count(session, user.id)
    text = t(
        user.locale,
        "referral.card",
        percent=settings.referral_percent,
        count=count,
        link=f"https://t.me/{bot_username}?start={user.id}",
    )
    await edit(callback, text, kb.back_to(user.locale))


@router.callback_query(MenuCB.filter(F.action == "support"))
async def open_support(callback: CallbackQuery, user: User, settings: Settings) -> None:
    links = []
    if settings.support_username:
        links.append(f"💬 @{settings.support_username}")
    if settings.channel_username:
        links.append(f"📣 @{settings.channel_username}")
    if settings.reviews_username:
        links.append(f"⭐️ @{settings.reviews_username}")

    body = "\n".join(links) if links else t(user.locale, "support.none")
    await edit(callback, t(user.locale, "support.card", links=body), kb.back_to(user.locale))


@router.callback_query(MenuCB.filter(F.action == "lang"))
async def open_language(callback: CallbackQuery, user: User) -> None:
    await edit(callback, t(user.locale, "language.choose"), kb.languages(user.locale))


@router.callback_query(LangCB.filter())
async def set_language(
    callback: CallbackQuery,
    callback_data: LangCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
    is_admin: bool,
) -> None:
    await user_service.set_locale(session, user, callback_data.code)
    await callback.answer(t(user.locale, "language.changed"))
    await edit(
        callback, menu_text(user, settings), kb.main_menu(user.locale, is_admin=is_admin)
    )
