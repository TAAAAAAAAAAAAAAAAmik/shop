"""Purchase flow: reserve stock, charge the wallet, hand over the goods.

Concurrency: two buyers must never receive the same stock item. On PostgreSQL
that is enforced with ``SELECT ... FOR UPDATE SKIP LOCKED``. SQLite has no row
locks, so the critical section is serialised with a process-wide asyncio lock —
correct for the single-process deployment SQLite is meant for.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.base import utcnow
from kinetix.db.models import Order, PromoCode, StockItem, TxKind, User
from kinetix.errors import (
    InsufficientFunds,
    InvalidQuantity,
    OutOfStock,
    ProductUnavailable,
)
from kinetix.money import apply_discount
from kinetix.services import promo as promo_service
from kinetix.services import wallet

_purchase_lock = asyncio.Lock()


@asynccontextmanager
async def _serialized(dialect: str) -> AsyncIterator[None]:
    if dialect == "postgresql":
        yield  # row-level locks below do the work
    else:
        async with _purchase_lock:
            yield


@dataclass(slots=True)
class Quote:
    quantity: int
    unit_price: int
    subtotal: int
    discount: int
    total: int
    promo: PromoCode | None = None


@dataclass(slots=True)
class Purchase:
    order_id: int
    quantity: int
    total: int
    balance_after: int
    payloads: list[str]


async def available_stock(session: AsyncSession, product_id: int) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(StockItem)
            .where(StockItem.product_id == product_id, StockItem.is_sold.is_(False))
        )
    ).scalar_one()


async def stock_map(session: AsyncSession, product_ids: list[int]) -> dict[int, int]:
    """Available count per product, for rendering a catalogue page in one query."""
    if not product_ids:
        return {}
    rows = await session.execute(
        select(StockItem.product_id, func.count())
        .where(StockItem.product_id.in_(product_ids), StockItem.is_sold.is_(False))
        .group_by(StockItem.product_id)
    )
    counts = dict(rows.all())
    return {pid: counts.get(pid, 0) for pid in product_ids}


async def quote(
    session: AsyncSession,
    *,
    user_id: int,
    product,
    quantity: int,
    promo_code: str | None = None,
) -> Quote:
    """Price an order without touching stock or balance."""
    if quantity < 1 or quantity > product.max_per_order:
        raise InvalidQuantity

    unit_price = product.unit_price(quantity)
    subtotal = unit_price * quantity

    promo = None
    discount = 0
    if promo_code:
        promo = await promo_service.validate(session, promo_code, user_id)
        discount = subtotal - apply_discount(subtotal, promo.percent)

    return Quote(
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        discount=discount,
        total=subtotal - discount,
        promo=promo,
    )


async def purchase(
    session: AsyncSession,
    *,
    dialect: str,
    user_id: int,
    product_id: int,
    quantity: int,
    promo_code: str | None = None,
) -> Purchase:
    """Execute a purchase end to end. Owns its transaction."""
    from kinetix.db.models import Product  # local import keeps the module import-light

    async with _serialized(dialect):
        try:
            user = await session.get(
                User, user_id, with_for_update=(dialect == "postgresql")
            )
            if user is None:
                raise ProductUnavailable

            product = await session.get(Product, product_id)
            if product is None or not product.is_active:
                raise ProductUnavailable

            priced = await quote(
                session,
                user_id=user_id,
                product=product,
                quantity=quantity,
                promo_code=promo_code,
            )

            stmt = (
                select(StockItem)
                .where(StockItem.product_id == product_id, StockItem.is_sold.is_(False))
                .order_by(StockItem.id)
                .limit(quantity)
            )
            if dialect == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            items = list((await session.execute(stmt)).scalars())

            if len(items) < quantity:
                raise OutOfStock(available=len(items))

            if user.balance < priced.total:
                raise InsufficientFunds(missing=priced.total - user.balance)

            order = Order(
                user_id=user.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=priced.unit_price,
                discount=priced.discount,
                total=priced.total,
                promo_code_id=priced.promo.id if priced.promo else None,
            )
            session.add(order)
            await session.flush()

            sold_at = utcnow()
            for item in items:
                item.is_sold = True
                item.order_id = order.id
                item.sold_at = sold_at

            await wallet.debit(
                session,
                user,
                priced.total,
                TxKind.PURCHASE,
                ref_id=order.id,
                comment=f"order #{order.id}",
            )
            user.total_spent += priced.total

            if priced.promo is not None:
                await promo_service.redeem(session, priced.promo, user.id, order.id)

            payloads = [item.payload for item in items]
            balance_after = user.balance

            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return Purchase(
        order_id=order.id,
        quantity=quantity,
        total=priced.total,
        balance_after=balance_after,
        payloads=payloads,
    )


async def user_orders(session: AsyncSession, user_id: int, limit: int = 10) -> list[Order]:
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(limit)
    )
    return list(result.scalars())
