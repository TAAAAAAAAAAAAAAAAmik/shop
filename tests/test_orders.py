import asyncio

import pytest
from sqlalchemy import func, select

from kinetix.db.models import BalanceTx, StockItem, TxKind
from kinetix.errors import InsufficientFunds, InvalidQuantity, OutOfStock
from kinetix.services import orders


async def test_purchase_delivers_and_charges(db, session, factory):
    user = await factory.user(balance=5000)
    product = await factory.product(price=1000, stock=5)

    result = await orders.purchase(
        session, dialect=db.dialect, user_id=user.id, product_id=product.id, quantity=3
    )

    assert result.total == 3000
    assert result.balance_after == 2000
    assert len(result.payloads) == 3
    assert len(set(result.payloads)) == 3
    assert await orders.available_stock(session, product.id) == 2

    tx = (await session.execute(select(BalanceTx))).scalars().all()
    assert [t.kind for t in tx] == [TxKind.PURCHASE]
    assert tx[0].amount == -3000
    assert tx[0].balance_after == 2000


async def test_bulk_tier_price_applies(db, session, factory):
    user = await factory.user(balance=100_000)
    product = await factory.product(price=100, stock=200, tiers={20: 90, 100: 80})

    cheap = await orders.purchase(
        session, dialect=db.dialect, user_id=user.id, product_id=product.id, quantity=10
    )
    assert cheap.total == 1000  # base price

    bulk = await orders.purchase(
        session, dialect=db.dialect, user_id=user.id, product_id=product.id, quantity=100
    )
    assert bulk.total == 8000  # 100 * 80


async def test_insufficient_funds_changes_nothing(db, session, factory):
    user = await factory.user(balance=500)
    product = await factory.product(price=1000, stock=5)
    # purchase() rolls back on failure, which expires ORM objects — read ids first.
    user_id, product_id = user.id, product.id

    with pytest.raises(InsufficientFunds) as exc:
        await orders.purchase(
            session, dialect=db.dialect, user_id=user_id, product_id=product_id, quantity=1
        )
    assert exc.value.missing == 500

    await session.refresh(user)
    assert user.balance == 500
    assert await orders.available_stock(session, product_id) == 5


async def test_out_of_stock_is_refused(db, session, factory):
    user = await factory.user(balance=100_000)
    product = await factory.product(price=100, stock=2)
    user_id, product_id = user.id, product.id

    with pytest.raises(OutOfStock) as exc:
        await orders.purchase(
            session, dialect=db.dialect, user_id=user_id, product_id=product_id, quantity=3
        )
    assert exc.value.available == 2

    await session.refresh(user)
    assert user.balance == 100_000


async def test_quantity_bounds(db, session, factory):
    user = await factory.user(balance=100_000)
    product = await factory.product(price=100, stock=10, max_per_order=5)
    user_id, product_id = user.id, product.id

    for bad in (0, -1, 6):
        with pytest.raises(InvalidQuantity):
            await orders.purchase(
                session,
                dialect=db.dialect,
                user_id=user_id,
                product_id=product_id,
                quantity=bad,
            )


async def test_concurrent_buyers_never_share_a_key(db, factory):
    """Ten buyers race for five keys: five win, nobody gets a duplicate."""
    async with db.session() as setup:
        product_factory = type(factory)(setup)
        product = await product_factory.product(price=100, stock=5)
        for uid in range(1, 11):
            await product_factory.user(user_id=uid, balance=10_000)

    async def buy(uid: int):
        async with db.session() as s:
            try:
                return await orders.purchase(
                    s, dialect=db.dialect, user_id=uid, product_id=product.id, quantity=1
                )
            except OutOfStock:
                return None

    results = await asyncio.gather(*(buy(uid) for uid in range(1, 11)))
    winners = [r for r in results if r is not None]
    assert len(winners) == 5

    payloads = [p for r in winners for p in r.payloads]
    assert len(set(payloads)) == 5

    async with db.session() as s:
        sold = (
            await s.execute(
                select(func.count()).select_from(StockItem).where(StockItem.is_sold.is_(True))
            )
        ).scalar_one()
        assert sold == 5
