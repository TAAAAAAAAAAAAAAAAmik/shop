"""Balance top-ups: invoice bookkeeping and idempotent crediting."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.base import utcnow
from kinetix.db.models import TopUp, TopUpStatus, TxKind, User
from kinetix.money import percent_of
from kinetix.services import wallet

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Credited:
    topup: TopUp
    balance_after: int
    referrer_id: int | None = None
    referral_bonus: int = 0


async def create(
    session: AsyncSession,
    *,
    user_id: int,
    provider: str,
    external_id: str,
    amount: int,
    pay_url: str | None = None,
    ttl_minutes: int = 60,
) -> TopUp:
    topup = TopUp(
        user_id=user_id,
        provider=provider,
        external_id=external_id,
        amount=amount,
        pay_url=pay_url,
        expires_at=utcnow() + timedelta(minutes=ttl_minutes),
    )
    session.add(topup)
    await session.commit()
    return topup


async def pending(session: AsyncSession, provider: str, limit: int = 100) -> list[TopUp]:
    result = await session.execute(
        select(TopUp)
        .where(TopUp.provider == provider, TopUp.status == TopUpStatus.PENDING)
        .order_by(TopUp.id)
        .limit(limit)
    )
    return list(result.scalars())


async def mark_paid(
    session: AsyncSession,
    topup_id: int,
    *,
    dialect: str = "sqlite",
    referral_percent: int = 0,
) -> Credited | None:
    """Credit a paid invoice exactly once.

    The status flip is a conditional UPDATE, so a duplicate webhook or an
    overlapping poll tick can never double-credit: the second caller sees
    rowcount 0 and gets ``None``.
    """
    try:
        result = await session.execute(
            update(TopUp)
            .where(TopUp.id == topup_id, TopUp.status == TopUpStatus.PENDING)
            .values(status=TopUpStatus.PAID, paid_at=utcnow())
        )
        if result.rowcount == 0:
            await session.rollback()
            return None

        topup = await session.get(TopUp, topup_id, populate_existing=True)
        assert topup is not None
        user = await session.get(
            User, topup.user_id, with_for_update=(dialect == "postgresql")
        )
        if user is None:  # pragma: no cover - FK makes this unreachable
            await session.rollback()
            return None

        await wallet.credit(
            session,
            user,
            topup.amount,
            TxKind.TOPUP,
            ref_id=topup.id,
            comment=f"{topup.provider} #{topup.external_id}",
        )

        referrer_id = None
        bonus = 0
        if referral_percent and user.referrer_id:
            bonus = percent_of(topup.amount, referral_percent)
            if bonus > 0:
                referrer = await session.get(
                    User, user.referrer_id, with_for_update=(dialect == "postgresql")
                )
                if referrer is not None and not referrer.is_banned:
                    await wallet.credit(
                        session,
                        referrer,
                        bonus,
                        TxKind.REFERRAL,
                        ref_id=topup.id,
                        comment=f"referral {user.id}",
                    )
                    referrer_id = referrer.id
                else:
                    bonus = 0

        balance_after = user.balance
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return Credited(
        topup=topup,
        balance_after=balance_after,
        referrer_id=referrer_id,
        referral_bonus=bonus,
    )


async def mark_status(session: AsyncSession, topup_id: int, status: TopUpStatus) -> bool:
    """Move a still-pending invoice to a terminal, non-crediting status."""
    result = await session.execute(
        update(TopUp)
        .where(TopUp.id == topup_id, TopUp.status == TopUpStatus.PENDING)
        .values(status=status)
    )
    await session.commit()
    return result.rowcount > 0


async def expire_stale(session: AsyncSession) -> int:
    result = await session.execute(
        update(TopUp)
        .where(TopUp.status == TopUpStatus.PENDING, TopUp.expires_at < utcnow())
        .values(status=TopUpStatus.EXPIRED)
    )
    await session.commit()
    return result.rowcount
