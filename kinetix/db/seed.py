"""Populate a fresh database with a demo catalogue.

    python -m kinetix.db.seed
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from kinetix.config import get_settings
from kinetix.db.base import Database
from kinetix.db.models import Category, PriceTier, Product, PromoCode, StockItem
from kinetix.logger import configure as configure_logging

log = logging.getLogger(__name__)


async def seed(db: Database) -> None:
    async with db.session() as session:
        existing = (
            await session.execute(select(func.count()).select_from(Category))
        ).scalar_one()
        if existing:
            log.info("catalogue already has %s categories, nothing to seed", existing)
            return

        subs = Category(title_ru="Подписки", title_en="Subscriptions", emoji="⭐️", sort_order=10)
        games = Category(title_ru="Игровые валюты", title_en="Game currency", emoji="🎮",
                         sort_order=20)
        session.add_all([subs, games])
        await session.flush()

        premium = Product(
            category_id=subs.id,
            title_ru="Демо-подписка, 1 месяц",
            title_en="Demo subscription, 1 month",
            description_ru="Пример товара с автовыдачей кода.",
            description_en="Example product with automatic code delivery.",
            price=29900,
        )
        coins = Product(
            category_id=games.id,
            title_ru="Демо-монеты, 100 шт.",
            title_en="Demo coins, 100 pcs",
            description_ru="Пример товара с оптовыми ценами.",
            description_en="Example product with bulk pricing.",
            price=5000,
        )
        session.add_all([premium, coins])
        await session.flush()

        session.add_all(
            [
                PriceTier(product_id=coins.id, min_qty=10, price=4500),
                PriceTier(product_id=coins.id, min_qty=50, price=4000),
            ]
        )
        session.add_all(
            [StockItem(product_id=premium.id, payload=f"DEMO-SUB-{i:04d}") for i in range(25)]
        )
        session.add_all(
            [StockItem(product_id=coins.id, payload=f"DEMO-COINS-{i:04d}") for i in range(200)]
        )
        session.add(PromoCode(code="WELCOME", percent=10, max_uses=100, per_user_limit=1))

        await session.commit()
        log.info("seeded 2 categories, 2 products, 225 stock items, promo WELCOME")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    db = Database(settings.database_url)
    await db.create_all()
    try:
        await seed(db)
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
