"""Loading deliverable stock into a product."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.i18n import t
from kinetix.keyboards import admin as kb
from kinetix.keyboards.callbacks import AdminCB
from kinetix.services import catalog as catalog_service
from kinetix.services import orders as order_service
from kinetix.states import AdminFlow
from kinetix.utils.tg import edit, escape

router = Router(name="admin.stock")

MAX_FILE_BYTES = 5 * 1024 * 1024


@router.callback_query(AdminCB.filter(F.action == "stock"))
async def choose_product(
    callback: CallbackQuery, session: AsyncSession, locale: str, state: FSMContext
) -> None:
    await state.clear()
    products = await catalog_service.all_products(session)
    if not products:
        await edit(callback, t(locale, "catalog.empty"), kb.back(locale))
        return
    await edit(
        callback, t(locale, "admin.stock.choose"), kb.pick_product(locale, products, "stock_pick")
    )


@router.callback_query(AdminCB.filter(F.action == "stock_pick"))
async def ask_payload(
    callback: CallbackQuery,
    callback_data: AdminCB,
    session: AsyncSession,
    locale: str,
    state: FSMContext,
) -> None:
    product = await catalog_service.get_product(session, callback_data.arg)
    if product is None:
        await callback.answer(t(locale, "error.stale"), show_alert=True)
        return
    await state.set_state(AdminFlow.stock_payload)
    await state.update_data(product_id=product.id)
    await edit(
        callback,
        t(locale, "admin.stock.ask", title=escape(product.title(locale))),
        kb.back(locale),
    )


@router.message(AdminFlow.stock_payload, F.document)
async def upload_file(
    message: Message, session: AsyncSession, locale: str, state: FSMContext, bot: Bot
) -> None:
    document = message.document
    if document is None:
        return
    if (document.file_size or 0) > MAX_FILE_BYTES:
        await message.answer(t(locale, "error.generic"))
        return

    buffer = await bot.download(document)
    if buffer is None:
        await message.answer(t(locale, "error.generic"))
        return
    raw = buffer.read().decode("utf-8", errors="replace")
    await _store(message, session, locale, state, raw)


@router.message(AdminFlow.stock_payload, F.text)
async def upload_text(
    message: Message, session: AsyncSession, locale: str, state: FSMContext
) -> None:
    await _store(message, session, locale, state, message.text or "")


async def _store(
    message: Message, session: AsyncSession, locale: str, state: FSMContext, raw: str
) -> None:
    data = await state.get_data()
    product_id = data.get("product_id")
    if not product_id:
        await state.clear()
        await message.answer(t(locale, "error.stale"))
        return

    report = await catalog_service.add_stock(session, product_id, raw)
    total = await order_service.available_stock(session, product_id)
    await state.clear()
    await message.answer(
        t(
            locale,
            "admin.stock.done",
            added=report.added,
            duplicates=report.duplicates,
            stock=total,
        ),
        reply_markup=kb.back(locale),
    )
