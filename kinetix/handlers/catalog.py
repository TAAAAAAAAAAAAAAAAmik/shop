"""Browsing the catalogue and buying."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.db.models import User
from kinetix.errors import (
    InsufficientFunds,
    InvalidQuantity,
    OutOfStock,
    ProductUnavailable,
    PromoError,
)
from kinetix.i18n import t
from kinetix.keyboards import user as kb
from kinetix.keyboards.callbacks import BuyCB, CategoryCB, MenuCB, ProductCB
from kinetix.money import format_money
from kinetix.services import catalog as catalog_service
from kinetix.services import notify
from kinetix.services import orders as order_service
from kinetix.services import promo as promo_service
from kinetix.states import BuyFlow
from kinetix.utils.tg import edit, escape, fits_in_message, goods_document

log = logging.getLogger(__name__)

router = Router(name="catalog")


async def _promo_from_state(state: FSMContext) -> str | None:
    return (await state.get_data()).get("promo_code")


async def _render_product(
    target: CallbackQuery,
    session: AsyncSession,
    user: User,
    settings: Settings,
    product_id: int,
    state: FSMContext,
) -> None:
    product = await catalog_service.get_product(session, product_id)
    if product is None or not product.is_active:
        await target.answer(t(user.locale, "order.unavailable"), show_alert=True)
        return

    stock = await order_service.available_stock(session, product.id)
    text = t(
        user.locale,
        "catalog.card",
        emoji=product.category.emoji,
        title=escape(product.title(user.locale)),
        description=escape(product.description(user.locale)) or "—",
        price=format_money(product.price, settings.currency),
        stock=stock,
    )
    if product.tiers:
        rows = "\n".join(
            t(
                user.locale,
                "catalog.tier_row",
                qty=tier.min_qty,
                price=format_money(tier.price, settings.currency),
            )
            for tier in product.tiers
        )
        text += t(user.locale, "catalog.tiers", rows=rows)
    if not stock:
        text += t(user.locale, "catalog.sold_out")

    promo_code = await _promo_from_state(state)
    await edit(
        target,
        text,
        kb.product_card(
            user.locale, product, in_stock=stock > 0, has_promo=bool(promo_code)
        ),
    )


@router.callback_query(MenuCB.filter(F.action == "catalog"))
async def open_catalog(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    categories = await catalog_service.active_categories(session)
    if not categories:
        await edit(callback, t(user.locale, "catalog.empty"), kb.back_to(user.locale))
        return
    await edit(callback, t(user.locale, "catalog.title"), kb.categories(user.locale, categories))


@router.callback_query(CategoryCB.filter())
async def open_category(
    callback: CallbackQuery,
    callback_data: CategoryCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    from kinetix.db.models import Category

    category = await session.get(Category, callback_data.category_id)
    if category is None:
        await callback.answer(t(user.locale, "error.stale"), show_alert=True)
        return

    products = await catalog_service.products_in(session, category.id)
    if not products:
        await edit(
            callback,
            t(user.locale, "catalog.category_empty"),
            kb.back_to(user.locale, "catalog"),
        )
        return

    stock = await order_service.stock_map(session, [p.id for p in products])
    text = t(
        user.locale,
        "catalog.category",
        emoji=category.emoji,
        title=escape(category.title(user.locale)),
    )
    await edit(callback, text, kb.products(user.locale, products, stock, settings.currency))


@router.callback_query(ProductCB.filter())
async def open_product(
    callback: CallbackQuery,
    callback_data: ProductCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
) -> None:
    await state.set_state(None)
    await _render_product(callback, session, user, settings, callback_data.product_id, state)


# --- promo ------------------------------------------------------------------


@router.callback_query(BuyCB.filter(F.action == "promo"))
async def ask_promo(
    callback: CallbackQuery, callback_data: BuyCB, user: User, state: FSMContext
) -> None:
    await state.set_state(BuyFlow.promo)
    await state.update_data(product_id=callback_data.product_id)
    await edit(callback, t(user.locale, "promo.ask"), kb.back_to(user.locale, "catalog"))


@router.callback_query(BuyCB.filter(F.action == "clear"))
async def clear_promo(
    callback: CallbackQuery,
    callback_data: BuyCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
) -> None:
    await state.update_data(promo_code=None)
    await callback.answer(t(user.locale, "promo.cleared"))
    await _render_product(callback, session, user, settings, callback_data.product_id, state)


@router.message(BuyFlow.promo, F.text)
async def apply_promo(
    message: Message,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    product_id = data.get("product_id")
    code = promo_service.normalize(message.text or "")

    try:
        promo = await promo_service.validate(session, code, user.id)
    except PromoError as exc:
        await message.answer(t(user.locale, f"promo.{exc.reason}"))
        return

    await state.update_data(promo_code=promo.code)
    await state.set_state(None)
    await message.answer(
        t(user.locale, "promo.applied", code=escape(promo.code), percent=promo.percent)
    )

    product = await catalog_service.get_product(session, product_id) if product_id else None
    if product is not None:
        stock = await order_service.available_stock(session, product.id)
        await message.answer(
            t(user.locale, "catalog.card",
              emoji=product.category.emoji,
              title=escape(product.title(user.locale)),
              description=escape(product.description(user.locale)) or "—",
              price=format_money(product.price, settings.currency),
              stock=stock),
            reply_markup=kb.product_card(
                user.locale, product, in_stock=stock > 0, has_promo=True
            ),
        )


# --- buy flow ---------------------------------------------------------------


@router.callback_query(BuyCB.filter(F.action == "start"))
async def ask_quantity(
    callback: CallbackQuery,
    callback_data: BuyCB,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    product = await catalog_service.get_product(session, callback_data.product_id)
    if product is None or not product.is_active:
        await callback.answer(t(user.locale, "order.unavailable"), show_alert=True)
        return

    stock = await order_service.available_stock(session, product.id)
    if stock <= 0:
        await callback.answer(t(user.locale, "order.out_of_stock", available=0), show_alert=True)
        return

    await state.set_state(BuyFlow.quantity)
    await state.update_data(product_id=product.id)
    await edit(
        callback,
        t(
            user.locale,
            "catalog.ask_quantity",
            title=escape(product.title(user.locale)),
            max=min(product.max_per_order, stock),
            stock=stock,
        ),
        kb.back_to(user.locale, "catalog"),
    )


@router.message(BuyFlow.quantity, F.text)
async def receive_quantity(
    message: Message,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(t(user.locale, "order.invalid_quantity"))
        return

    data = await state.get_data()
    product = await catalog_service.get_product(session, data.get("product_id", 0))
    if product is None:
        await state.clear()
        await message.answer(t(user.locale, "error.stale"))
        return

    try:
        priced = await order_service.quote(
            session,
            user_id=user.id,
            product=product,
            quantity=int(raw),
            promo_code=data.get("promo_code"),
        )
    except InvalidQuantity:
        await message.answer(t(user.locale, "order.invalid_quantity"))
        return
    except PromoError as exc:
        await state.update_data(promo_code=None)
        await message.answer(t(user.locale, f"promo.{exc.reason}"))
        return

    available = await order_service.available_stock(session, product.id)
    if available < priced.quantity:
        await message.answer(t(user.locale, "order.out_of_stock", available=available))
        return

    promo_line = ""
    if priced.promo is not None:
        promo_line = t(
            user.locale,
            "order.promo_line",
            code=escape(priced.promo.code),
            percent=priced.promo.percent,
            discount=format_money(priced.discount, settings.currency),
        )

    await state.update_data(quantity=priced.quantity)
    await state.set_state(None)
    await message.answer(
        t(
            user.locale,
            "order.confirm",
            title=escape(product.title(user.locale)),
            quantity=priced.quantity,
            unit=format_money(priced.unit_price, settings.currency),
            promo_line=promo_line,
            total=format_money(priced.total, settings.currency),
            balance=format_money(user.balance, settings.currency),
        ),
        reply_markup=kb.confirm_order(user.locale, product.id),
    )


@router.callback_query(BuyCB.filter(F.action == "confirm"))
async def confirm_purchase(
    callback: CallbackQuery,
    callback_data: BuyCB,
    session: AsyncSession,
    user: User,
    settings: Settings,
    state: FSMContext,
    dialect: str,
    bot: Bot,
) -> None:
    data = await state.get_data()
    quantity = int(data.get("quantity", 0))
    product = await catalog_service.get_product(session, callback_data.product_id)
    if product is None or quantity < 1:
        await callback.answer(t(user.locale, "error.stale"), show_alert=True)
        return

    # purchase() rolls back on failure, which expires ORM instances — keep what we need.
    locale = user.locale
    title = product.title(locale)
    user_mention = user.mention

    try:
        result = await order_service.purchase(
            session,
            dialect=dialect,
            user_id=user.id,
            product_id=product.id,
            quantity=quantity,
            promo_code=data.get("promo_code"),
        )
    except InsufficientFunds as exc:
        await edit(
            callback,
            t(
                locale,
                "order.insufficient",
                missing=format_money(exc.missing, settings.currency),
            ),
            kb.back_to(locale),
        )
        return
    except OutOfStock as exc:
        await edit(
            callback,
            t(locale, "order.out_of_stock", available=exc.available),
            kb.back_to(locale, "catalog"),
        )
        return
    except (InvalidQuantity, ProductUnavailable):
        await edit(callback, t(locale, "order.unavailable"), kb.back_to(locale))
        return
    except PromoError as exc:
        await state.update_data(promo_code=None)
        await edit(callback, t(locale, f"promo.{exc.reason}"), kb.back_to(locale))
        return

    await state.clear()
    await edit(
        callback,
        t(
            locale,
            "order.success",
            order_id=result.order_id,
            title=escape(title),
            quantity=result.quantity,
            total=format_money(result.total, settings.currency),
            balance=format_money(result.balance_after, settings.currency),
        ),
        kb.back_to(locale),
    )

    if callback.message is not None:
        if fits_in_message(result.payloads):
            body = "\n".join(f"<code>{escape(p)}</code>" for p in result.payloads)
            await callback.message.answer(t(locale, "order.goods", payloads=body))
        else:
            await callback.message.answer_document(
                goods_document(result.payloads, result.order_id),
                caption=t(locale, "order.goods_file", quantity=result.quantity),
            )

    asyncio.create_task(  # noqa: RUF006 - fire and forget, errors are logged inside
        notify.admins(
            bot,
            settings.admin_ids,
            t(
                "ru",
                "admin.notify.order",
                order_id=result.order_id,
                user=escape(user_mention),
                title=escape(title),
                quantity=result.quantity,
                total=format_money(result.total, settings.currency),
            ),
        )
    )
