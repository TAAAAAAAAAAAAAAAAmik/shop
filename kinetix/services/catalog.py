"""Catalogue reads and admin-side stock management."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.models import Category, PriceTier, Product, StockItem


@dataclass(slots=True)
class StockUpload:
    added: int
    duplicates: int
    blank: int


async def active_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.id)
    )
    return list(result.scalars())


async def all_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category).order_by(Category.sort_order, Category.id))
    return list(result.scalars())


async def products_in(
    session: AsyncSession, category_id: int, *, only_active: bool = True
) -> list[Product]:
    stmt = select(Product).where(Product.category_id == category_id)
    if only_active:
        stmt = stmt.where(Product.is_active.is_(True))
    result = await session.execute(stmt.order_by(Product.sort_order, Product.id))
    return list(result.scalars())


async def all_products(session: AsyncSession) -> list[Product]:
    result = await session.execute(select(Product).order_by(Product.category_id, Product.id))
    return list(result.scalars())


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def create_category(
    session: AsyncSession, *, title_ru: str, title_en: str, emoji: str = "📦"
) -> Category:
    category = Category(title_ru=title_ru, title_en=title_en, emoji=emoji)
    session.add(category)
    await session.commit()
    return category


async def create_product(
    session: AsyncSession,
    *,
    category_id: int,
    title_ru: str,
    title_en: str,
    price: int,
    description_ru: str = "",
    description_en: str = "",
) -> Product:
    product = Product(
        category_id=category_id,
        title_ru=title_ru,
        title_en=title_en,
        price=price,
        description_ru=description_ru,
        description_en=description_en,
    )
    session.add(product)
    await session.commit()
    return product


async def set_price(session: AsyncSession, product: Product, price: int) -> None:
    product.price = price
    await session.commit()


async def set_tier(session: AsyncSession, product_id: int, min_qty: int, price: int) -> PriceTier:
    """Add or update a bulk-pricing tier."""
    tier = (
        await session.execute(
            select(PriceTier).where(
                PriceTier.product_id == product_id, PriceTier.min_qty == min_qty
            )
        )
    ).scalar_one_or_none()
    if tier is None:
        tier = PriceTier(product_id=product_id, min_qty=min_qty, price=price)
        session.add(tier)
    else:
        tier.price = price
    await session.commit()
    return tier


async def toggle_product(session: AsyncSession, product: Product) -> bool:
    product.is_active = not product.is_active
    await session.commit()
    return product.is_active


async def add_stock(session: AsyncSession, product_id: int, raw: str) -> StockUpload:
    """Load stock from newline-separated text, skipping blanks and duplicates."""
    lines = [line.strip() for line in (raw or "").splitlines()]
    blank = sum(1 for line in lines if not line)
    candidates: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            candidates.append(line)

    if not candidates:
        return StockUpload(added=0, duplicates=0, blank=blank)

    existing = set(
        (
            await session.execute(
                select(StockItem.payload).where(
                    StockItem.product_id == product_id, StockItem.payload.in_(candidates)
                )
            )
        ).scalars()
    )
    fresh = [payload for payload in candidates if payload not in existing]
    session.add_all(
        [StockItem(product_id=product_id, payload=payload) for payload in fresh]
    )
    await session.commit()

    duplicates = (len(lines) - blank) - len(fresh)
    return StockUpload(added=len(fresh), duplicates=duplicates, blank=blank)
