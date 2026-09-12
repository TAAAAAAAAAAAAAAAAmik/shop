"""Balance mutations.

Every change goes through :func:`apply_tx`, which writes an append-only
``BalanceTx`` row alongside the new balance. Nothing else may touch
``User.balance`` directly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.models import BalanceTx, TxKind, User
from kinetix.errors import InsufficientFunds


async def apply_tx(
    session: AsyncSession,
    user: User,
    amount: int,
    kind: TxKind,
    *,
    ref_id: int | None = None,
    comment: str = "",
) -> BalanceTx:
    """Move `amount` (signed, minor units) on the user's wallet.

    Raises :class:`InsufficientFunds` if the result would go negative.
    Does not commit — the caller owns the transaction.
    """
    new_balance = user.balance + amount
    if new_balance < 0:
        raise InsufficientFunds(missing=-new_balance)

    user.balance = new_balance
    tx = BalanceTx(
        user_id=user.id,
        amount=amount,
        balance_after=new_balance,
        kind=kind,
        ref_id=ref_id,
        comment=comment[:256],
    )
    session.add(tx)
    return tx


async def credit(
    session: AsyncSession,
    user: User,
    amount: int,
    kind: TxKind,
    *,
    ref_id: int | None = None,
    comment: str = "",
) -> BalanceTx:
    if amount < 0:
        raise ValueError("credit() takes a non-negative amount")
    return await apply_tx(session, user, amount, kind, ref_id=ref_id, comment=comment)


async def debit(
    session: AsyncSession,
    user: User,
    amount: int,
    kind: TxKind,
    *,
    ref_id: int | None = None,
    comment: str = "",
) -> BalanceTx:
    if amount < 0:
        raise ValueError("debit() takes a non-negative amount")
    return await apply_tx(session, user, -amount, kind, ref_id=ref_id, comment=comment)


async def history(session: AsyncSession, user_id: int, limit: int = 10) -> list[BalanceTx]:
    result = await session.execute(
        select(BalanceTx)
        .where(BalanceTx.user_id == user_id)
        .order_by(BalanceTx.id.desc())
        .limit(limit)
    )
    return list(result.scalars())
