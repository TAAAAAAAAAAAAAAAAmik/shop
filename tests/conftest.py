from __future__ import annotations

import pytest_asyncio

from kinetix.db.base import Database
from kinetix.db.models import Category, PriceTier, Product, StockItem, User


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.create_all()
    yield database
    await database.dispose()


@pytest_asyncio.fixture
async def session(db):
    async with db.session() as s:
        yield s


@pytest_asyncio.fixture
async def factory(session):
    return Factory(session)


class Factory:
    """Small helpers so tests read as scenarios, not as ORM boilerplate."""

    def __init__(self, session):
        self.session = session

    async def user(self, user_id: int = 1, balance: int = 0, **kwargs) -> User:
        user = User(id=user_id, username=f"u{user_id}", balance=balance, **kwargs)
        self.session.add(user)
        await self.session.commit()
        return user

    async def product(
        self,
        price: int = 1000,
        stock: int = 0,
        tiers: dict[int, int] | None = None,
        **kwargs,
    ) -> Product:
        category = Category(title_ru="Тест", title_en="Test")
        self.session.add(category)
        await self.session.flush()

        product = Product(
            category_id=category.id,
            title_ru="Товар",
            title_en="Item",
            price=price,
            **kwargs,
        )
        self.session.add(product)
        await self.session.flush()

        for min_qty, tier_price in (tiers or {}).items():
            self.session.add(
                PriceTier(product_id=product.id, min_qty=min_qty, price=tier_price)
            )
        for i in range(stock):
            self.session.add(StockItem(product_id=product.id, payload=f"KEY-{i:04d}"))

        await self.session.commit()
        await self.session.refresh(product)
        return product
