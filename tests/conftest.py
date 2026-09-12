from __future__ import annotations

import pytest
import pytest_asyncio
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from kinetix.__main__ import build_dispatcher
from kinetix.config import Settings
from kinetix.db.base import Database
from kinetix.db.models import Category, PriceTier, Product, StockItem, User
from tests.mocked_bot import BOT_USERNAME, make_bot
from tests.updates import ADMIN_ID

REQUISITES = "Сбербанк 2202 2020 1111 2222\nПолучатель: И. И. Иванов"


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


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        BOT_TOKEN="424242:TEST-TOKEN-FOR-UNIT-TESTS",
        ADMIN_IDS=str(ADMIN_ID),
        SHOP_NAME="Kinetix",
        THROTTLE_RATE=0,  # no rate limiting inside tests
        CRYPTO_PAY_TOKEN="",
        MANUAL_REQUISITES=REQUISITES,
        DEFAULT_LOCALE="ru",
    )


# aiogram Routers are module-level singletons and can only be attached to one
# Dispatcher, so the dispatcher is built once and re-pointed at each test's
# database through workflow data.
_dispatcher: Dispatcher | None = None


@pytest_asyncio.fixture
async def app(db, settings):
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = build_dispatcher(db, settings, crypto=None)

    dp = _dispatcher
    dp["database"] = db
    dp["settings"] = settings
    dp["crypto"] = None
    dp["bot_username"] = BOT_USERNAME
    dp.fsm.storage = MemoryStorage()  # no FSM leakage between tests

    bot, session = make_bot()
    yield dp, bot, session
    await bot.session.close()
