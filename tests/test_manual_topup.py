"""Manual bank transfers: request → claim → staff review."""

import asyncio

from sqlalchemy import func, select

from kinetix.db.base import utcnow
from kinetix.db.models import BalanceTx, TopUp, TopUpStatus, TxKind, User
from kinetix.services import topups

ADMIN = 500


async def open_request(session, user, amount=50_000) -> TopUp:
    topup = await topups.create_manual(session, user_id=user.id, amount=amount)
    await topups.submit_for_review(session, topup.id)
    return topup


async def test_reference_is_unique_and_readable(db, session, factory):
    user = await factory.user()
    refs = {
        (await topups.create_manual(session, user_id=user.id, amount=1000)).external_id
        for _ in range(20)
    }
    assert len(refs) == 20
    for ref in refs:
        assert ref.startswith("KNX-")
        assert not set(ref[4:]) & set("01OI")  # no look-alike characters


async def test_request_lifecycle(db, session, factory):
    user = await factory.user(balance=0)
    topup = await topups.create_manual(session, user_id=user.id, amount=50_000)
    assert topup.status is TopUpStatus.PENDING
    assert (await topups.open_manual(session, user.id)).id == topup.id

    submitted = await topups.submit_for_review(session, topup.id)
    assert submitted is not None
    assert submitted.status is TopUpStatus.AWAITING_REVIEW
    assert submitted.submitted_at is not None

    # Claiming twice must not queue a second review.
    assert await topups.submit_for_review(session, topup.id) is None
    assert len(await topups.awaiting_review(session)) == 1


async def test_approval_credits_once(db, session, factory):
    user = await factory.user(balance=0)
    # A no-op approve rolls back and expires ORM objects, so keep the raw id.
    topup_id = (await open_request(session, user)).id

    credited = await topups.approve(session, topup_id, admin_id=ADMIN, dialect=db.dialect)
    assert credited is not None
    assert credited.balance_after == 50_000

    # A second tap on "approve" is a no-op.
    assert await topups.approve(session, topup_id, admin_id=ADMIN, dialect=db.dialect) is None

    await session.refresh(user)
    assert user.balance == 50_000
    assert (
        await session.execute(
            select(func.count()).select_from(BalanceTx).where(BalanceTx.kind == TxKind.TOPUP)
        )
    ).scalar_one() == 1

    stored = await session.get(TopUp, topup_id, populate_existing=True)
    assert stored.reviewed_by == ADMIN
    assert stored.reviewed_at is not None


async def test_unclaimed_request_cannot_be_approved(db, session, factory):
    user = await factory.user(balance=0)
    topup_id = (await topups.create_manual(session, user_id=user.id, amount=10_000)).id

    assert await topups.approve(session, topup_id, admin_id=ADMIN, dialect=db.dialect) is None
    await session.refresh(user)
    assert user.balance == 0


async def test_rejection_credits_nothing_and_is_final(db, session, factory):
    user = await factory.user(balance=0)
    topup_id = (await open_request(session, user, amount=99_000)).id

    rejected = await topups.reject(session, topup_id, admin_id=ADMIN)
    assert rejected is not None
    assert rejected.status is TopUpStatus.REJECTED

    assert await topups.approve(session, topup_id, admin_id=ADMIN, dialect=db.dialect) is None
    assert await topups.reject(session, topup_id, admin_id=ADMIN) is None

    await session.refresh(user)
    assert user.balance == 0


async def test_two_admins_approving_at_once_credit_once(db, factory):
    async with db.session() as setup:
        f = type(factory)(setup)
        user = await f.user(balance=0)
        topup = await topups.create_manual(setup, user_id=user.id, amount=25_000)
        await topups.submit_for_review(setup, topup.id)
        topup_id, user_id = topup.id, user.id

    async def approve(admin_id: int):
        async with db.session() as s:
            return await topups.approve(
                s, topup_id, admin_id=admin_id, dialect=db.dialect
            )

    results = await asyncio.gather(*(approve(admin) for admin in range(1, 6)))
    assert sum(1 for r in results if r is not None) == 1

    async with db.session() as s:
        assert (await s.get(User, user_id)).balance == 25_000


async def test_approval_pays_the_referrer(db, session, factory):
    inviter = await factory.user(user_id=10, balance=0)
    invited = await factory.user(user_id=20, balance=0, referrer_id=inviter.id)
    topup = await open_request(session, invited, amount=200_000)

    credited = await topups.approve(
        session, topup.id, admin_id=ADMIN, dialect=db.dialect, referral_percent=5
    )
    assert credited.referral_bonus == 10_000

    await session.refresh(inviter)
    assert inviter.balance == 10_000


async def test_cancel_frees_the_slot(db, session, factory):
    user = await factory.user()
    topup = await topups.create_manual(session, user_id=user.id, amount=10_000)

    assert await topups.cancel(session, topup.id, user.id) is True
    assert await topups.open_manual(session, user.id) is None
    # A claimed request can no longer be cancelled by the payer.
    other = await open_request(session, user)
    assert await topups.cancel(session, other.id, user.id) is False


async def test_claimed_requests_survive_expiry_sweep(db, session, factory):
    """A request under review must not be swept away while staff look at it."""
    user = await factory.user()
    stale = await topups.create_manual(session, user_id=user.id, amount=10_000)
    claimed = await open_request(session, user, amount=20_000)

    for topup in (stale, claimed):
        topup.expires_at = utcnow().replace(year=2000)
    await session.commit()

    await topups.expire_stale(session)

    assert (await session.get(TopUp, stale.id, populate_existing=True)).status is (
        TopUpStatus.EXPIRED
    )
    assert (await session.get(TopUp, claimed.id, populate_existing=True)).status is (
        TopUpStatus.AWAITING_REVIEW
    )
