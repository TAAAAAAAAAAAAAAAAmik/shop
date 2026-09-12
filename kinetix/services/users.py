"""User lifecycle: registration, locale, referrals, moderation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.base import utcnow
from kinetix.db.models import Order, User


@dataclass(slots=True)
class ShopStats:
    users: int
    banned: int
    orders: int
    revenue: int
    balances: int


async def get_or_create(
    session: AsyncSession,
    *,
    user_id: int,
    username: str | None,
    first_name: str | None,
    locale: str,
    referrer_id: int | None = None,
) -> tuple[User, bool]:
    """Fetch the user, creating them on first contact. Returns (user, created)."""
    user = await session.get(User, user_id)
    if user is not None:
        user.username = username
        user.first_name = first_name
        user.last_seen_at = utcnow()
        await session.commit()
        return user, False

    # A referrer only counts if they exist and aren't the new user themselves.
    valid_referrer = None
    if referrer_id and referrer_id != user_id:
        if await session.get(User, referrer_id) is not None:
            valid_referrer = referrer_id

    user = User(
        id=user_id,
        username=username,
        first_name=first_name,
        locale=locale,
        referrer_id=valid_referrer,
        last_seen_at=utcnow(),
    )
    session.add(user)
    await session.commit()
    return user, True


async def set_locale(session: AsyncSession, user: User, locale: str) -> None:
    user.locale = locale
    await session.commit()


async def set_banned(session: AsyncSession, user_id: int, banned: bool) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.is_banned = banned
    await session.commit()
    return user


async def referral_count(session: AsyncSession, user_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(User).where(User.referrer_id == user_id)
        )
    ).scalar_one()


async def find(session: AsyncSession, query: str) -> User | None:
    """Look a user up by numeric id or @username."""
    query = query.strip().lstrip("@")
    if query.isdigit():
        return await session.get(User, int(query))
    return (
        await session.execute(select(User).where(func.lower(User.username) == query.lower()))
    ).scalar_one_or_none()


async def all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.id).where(User.is_banned.is_(False)))
    return list(result.scalars())


async def stats(session: AsyncSession) -> ShopStats:
    users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    banned = (
        await session.execute(
            select(func.count()).select_from(User).where(User.is_banned.is_(True))
        )
    ).scalar_one()
    orders = (await session.execute(select(func.count()).select_from(Order))).scalar_one()
    revenue = (await session.execute(select(func.coalesce(func.sum(Order.total), 0)))).scalar_one()
    balances = (
        await session.execute(select(func.coalesce(func.sum(User.balance), 0)))
    ).scalar_one()
    return ShopStats(
        users=users, banned=banned, orders=orders, revenue=revenue, balances=balances
    )
