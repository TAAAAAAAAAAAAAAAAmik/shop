"""Promo-code validation and redemption."""

from __future__ import annotations

from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.base import utcnow
from kinetix.db.models import PromoCode, PromoUse
from kinetix.errors import (
    PromoAlreadyUsed,
    PromoExhausted,
    PromoExpired,
    PromoNotFound,
)

MAX_CODE_LEN = 32


def normalize(code: str) -> str:
    return (code or "").strip().upper()[:MAX_CODE_LEN]


async def validate(session: AsyncSession, code: str, user_id: int) -> PromoCode:
    """Return the usable promo, or raise a :class:`PromoError` subclass."""
    promo = (
        await session.execute(select(PromoCode).where(PromoCode.code == normalize(code)))
    ).scalar_one_or_none()

    if promo is None or not promo.is_active:
        raise PromoNotFound

    if promo.expires_at is not None:
        expires_at = promo.expires_at
        if expires_at.tzinfo is None:  # SQLite hands back naive datetimes
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= utcnow():
            raise PromoExpired

    if promo.max_uses and promo.used_count >= promo.max_uses:
        raise PromoExhausted

    if promo.per_user_limit:
        used_by_user = (
            await session.execute(
                select(func.count())
                .select_from(PromoUse)
                .where(PromoUse.promo_code_id == promo.id, PromoUse.user_id == user_id)
            )
        ).scalar_one()
        if used_by_user >= promo.per_user_limit:
            raise PromoAlreadyUsed

    return promo


async def redeem(
    session: AsyncSession, promo: PromoCode, user_id: int, order_id: int | None = None
) -> PromoUse:
    """Record a use. Caller must have validated the promo in the same transaction."""
    promo.used_count += 1
    use = PromoUse(promo_code_id=promo.id, user_id=user_id, order_id=order_id)
    session.add(use)
    return use
