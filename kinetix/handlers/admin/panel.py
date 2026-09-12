"""Admin dashboard: menu, statistics, product overview."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.i18n import t
from kinetix.keyboards import admin as kb
from kinetix.keyboards.callbacks import AdminCB
from kinetix.money import format_money
from kinetix.services import catalog as catalog_service
from kinetix.services import orders as order_service
from kinetix.services import users as user_service
from kinetix.utils.tg import edit, escape

router = Router(name="admin.panel")


@router.message(Command("admin"))
async def cmd_admin(message: Message, locale: str, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t(locale, "admin.menu"), reply_markup=kb.menu(locale))


@router.callback_query(AdminCB.filter(F.action == "menu"))
async def open_menu(callback: CallbackQuery, locale: str, state: FSMContext) -> None:
    await state.clear()
    await edit(callback, t(locale, "admin.menu"), kb.menu(locale))


@router.callback_query(AdminCB.filter(F.action == "stats"))
async def show_stats(
    callback: CallbackQuery, session: AsyncSession, locale: str, settings: Settings
) -> None:
    stats = await user_service.stats(session)
    await edit(
        callback,
        t(
            locale,
            "admin.stats",
            users=stats.users,
            banned=stats.banned,
            orders=stats.orders,
            revenue=format_money(stats.revenue, settings.currency),
            balances=format_money(stats.balances, settings.currency),
        ),
        kb.back(locale),
    )


@router.callback_query(AdminCB.filter(F.action == "products"))
async def list_products(
    callback: CallbackQuery, session: AsyncSession, locale: str, settings: Settings
) -> None:
    products = await catalog_service.all_products(session)
    text = t(locale, "admin.products.list")
    if not products:
        text += "\n\n" + t(locale, "catalog.empty")
    else:
        stock = await order_service.stock_map(session, [p.id for p in products])
        rows = "\n".join(
            t(
                locale,
                "admin.products.row",
                id=product.id,
                title=escape(product.title(locale)),
                price=format_money(product.price, settings.currency),
                stock=stock.get(product.id, 0),
                state="" if product.is_active else "🚫",
            )
            for product in products
        )
        text += "\n\n" + rows
    await edit(callback, text, kb.back(locale))
