import asyncio

from sqlalchemy import func, select

from kinetix.db.models import BalanceTx, TopUpStatus, TxKind
from kinetix.services import topups


async def test_paid_invoice_credits_once(db, session, factory):
    user = await factory.user(balance=0)
    topup = await topups.create(
        session, user_id=user.id, provider="cryptobot", external_id="inv-1", amount=50_000
    )

    first = await topups.mark_paid(session, topup.id, dialect=db.dialect)
    assert first is not None
    assert first.balance_after == 50_000

    # A duplicate webhook / overlapping poll tick must be a no-op.
    second = await topups.mark_paid(session, topup.id, dialect=db.dialect)
    assert second is None

    await session.refresh(user)
    assert user.balance == 50_000
    count = (
        await session.execute(
            select(func.count()).select_from(BalanceTx).where(BalanceTx.kind == TxKind.TOPUP)
        )
    ).scalar_one()
    assert count == 1


async def test_concurrent_credit_attempts_credit_once(db, factory):
    async with db.session() as setup:
        f = type(factory)(setup)
        user = await f.user(balance=0)
        topup = await topups.create(
            setup, user_id=user.id, provider="cryptobot", external_id="inv-2", amount=10_000
        )
        topup_id, user_id = topup.id, user.id

    async def credit():
        async with db.session() as s:
            return await topups.mark_paid(s, topup_id, dialect=db.dialect)

    results = await asyncio.gather(*(credit() for _ in range(5)))
    assert sum(1 for r in results if r is not None) == 1

    async with db.session() as s:
        assert (await s.get(type(user), user_id)).balance == 10_000


async def test_referral_bonus_goes_to_inviter(db, session, factory):
    inviter = await factory.user(user_id=100, balance=0)
    invited = await factory.user(user_id=200, balance=0, referrer_id=inviter.id)

    topup = await topups.create(
        session, user_id=invited.id, provider="cryptobot", external_id="inv-3", amount=100_000
    )
    credited = await topups.mark_paid(
        session, topup.id, dialect=db.dialect, referral_percent=5
    )

    assert credited is not None
    assert credited.referrer_id == inviter.id
    assert credited.referral_bonus == 5_000

    await session.refresh(inviter)
    await session.refresh(invited)
    assert invited.balance == 100_000
    assert inviter.balance == 5_000


async def test_banned_inviter_gets_nothing(db, session, factory):
    inviter = await factory.user(user_id=100, balance=0, is_banned=True)
    invited = await factory.user(user_id=200, balance=0, referrer_id=inviter.id)

    topup = await topups.create(
        session, user_id=invited.id, provider="cryptobot", external_id="inv-4", amount=100_000
    )
    credited = await topups.mark_paid(
        session, topup.id, dialect=db.dialect, referral_percent=5
    )

    assert credited is not None
    assert credited.referral_bonus == 0
    await session.refresh(inviter)
    assert inviter.balance == 0


async def test_expired_invoice_is_not_credited(db, session, factory):
    user = await factory.user(balance=0)
    topup = await topups.create(
        session, user_id=user.id, provider="cryptobot", external_id="inv-5", amount=1_000
    )

    assert await topups.mark_status(session, topup.id, TopUpStatus.EXPIRED) is True
    assert await topups.mark_paid(session, topup.id, dialect=db.dialect) is None

    await session.refresh(user)
    assert user.balance == 0
