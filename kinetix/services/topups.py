"""Balance top-ups: invoice bookkeeping and idempotent crediting.

Two payment routes share this module:

* **cryptobot** — the provider confirms the invoice, the poller credits it.
* **manual** — the payer transfers to bank details shown by the bot, presses
  "I paid", and a staff member approves or rejects after checking the account.

Every state change is a conditional UPDATE guarded on the current status, so a
repeated webhook, an overlapping poll tick or two admins tapping "approve"
together can only ever take effect once.

Note for callers: the "nothing to do" paths roll back, which expires ORM
instances attached to the session. Hold plain ids across these calls rather
than model objects.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.base import utcnow
from kinetix.db.models import TopUp, TopUpStatus, TxKind, User
from kinetix.money import percent_of
from kinetix.services import wallet

log = logging.getLogger(__name__)

MANUAL_PROVIDER = "manual"
# No 0/O/1/I: these codes get read off a screen and typed into a bank app.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
REFERENCE_PREFIX = "KNX"


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


def make_reference() -> str:
    body = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))
    return f"{REFERENCE_PREFIX}-{body}"


async def create_manual(
    session: AsyncSession, *, user_id: int, amount: int, ttl_minutes: int = 60
) -> TopUp:
    """Open a manual transfer request with a unique, human-readable reference."""
    for _ in range(5):
        reference = make_reference()
        clash = (
            await session.execute(
                select(TopUp.id).where(
                    TopUp.provider == MANUAL_PROVIDER, TopUp.external_id == reference
                )
            )
        ).first()
        if clash is None:
            break
    else:  # pragma: no cover - 32^6 space, five clashes in a row is not realistic
        raise RuntimeError("could not allocate a payment reference")

    return await create(
        session,
        user_id=user_id,
        provider=MANUAL_PROVIDER,
        external_id=reference,
        amount=amount,
        ttl_minutes=ttl_minutes,
    )


async def open_manual(session: AsyncSession, user_id: int) -> TopUp | None:
    """The user's current unfinished manual request, if any."""
    result = await session.execute(
        select(TopUp)
        .where(
            TopUp.user_id == user_id,
            TopUp.provider == MANUAL_PROVIDER,
            or_(
                TopUp.status == TopUpStatus.PENDING,
                TopUp.status == TopUpStatus.AWAITING_REVIEW,
            ),
        )
        .order_by(TopUp.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def submit_for_review(session: AsyncSession, topup_id: int) -> TopUp | None:
    """Payer pressed "I paid". Only a still-pending request can be submitted."""
    result = await session.execute(
        update(TopUp)
        .where(TopUp.id == topup_id, TopUp.status == TopUpStatus.PENDING)
        .values(status=TopUpStatus.AWAITING_REVIEW, submitted_at=utcnow())
    )
    if result.rowcount == 0:
        await session.rollback()
        return None
    await session.commit()
    return await session.get(TopUp, topup_id, populate_existing=True)


async def awaiting_review(session: AsyncSession, limit: int = 50) -> list[TopUp]:
    result = await session.execute(
        select(TopUp)
        .where(TopUp.status == TopUpStatus.AWAITING_REVIEW)
        .order_by(TopUp.id)
        .limit(limit)
    )
    return list(result.scalars())


async def approve(
    session: AsyncSession,
    topup_id: int,
    *,
    admin_id: int,
    dialect: str = "sqlite",
    referral_percent: int = 0,
) -> Credited | None:
    """Credit a manual transfer the admin has confirmed in their bank."""
    return await mark_paid(
        session,
        topup_id,
        dialect=dialect,
        referral_percent=referral_percent,
        from_status=TopUpStatus.AWAITING_REVIEW,
        reviewed_by=admin_id,
    )


async def reject(session: AsyncSession, topup_id: int, *, admin_id: int) -> TopUp | None:
    """Turn down a claimed transfer. Credits nothing."""
    result = await session.execute(
        update(TopUp)
        .where(TopUp.id == topup_id, TopUp.status == TopUpStatus.AWAITING_REVIEW)
        .values(status=TopUpStatus.REJECTED, reviewed_by=admin_id, reviewed_at=utcnow())
    )
    if result.rowcount == 0:
        await session.rollback()
        return None
    await session.commit()
    return await session.get(TopUp, topup_id, populate_existing=True)


async def cancel(session: AsyncSession, topup_id: int, user_id: int) -> bool:
    """Payer abandoned the transfer before claiming it."""
    result = await session.execute(
        update(TopUp)
        .where(
            TopUp.id == topup_id,
            TopUp.user_id == user_id,
            TopUp.status == TopUpStatus.PENDING,
        )
        .values(status=TopUpStatus.CANCELLED)
    )
    await session.commit()
    return result.rowcount > 0


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
    from_status: TopUpStatus = TopUpStatus.PENDING,
    reviewed_by: int | None = None,
) -> Credited | None:
    """Credit a top-up exactly once.

    The status flip is a conditional UPDATE, so a duplicate webhook, an
    overlapping poll tick or two admins tapping "approve" at the same moment
    can never double-credit: the second caller sees rowcount 0 and gets
    ``None``. ``from_status`` is PENDING for provider-confirmed invoices and
    AWAITING_REVIEW for manually reviewed transfers.
    """
    try:
        values: dict[str, object] = {"status": TopUpStatus.PAID, "paid_at": utcnow()}
        if reviewed_by is not None:
            values["reviewed_by"] = reviewed_by
            values["reviewed_at"] = utcnow()

        result = await session.execute(
            update(TopUp)
            .where(TopUp.id == topup_id, TopUp.status == from_status)
            .values(**values)
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
