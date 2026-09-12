from datetime import timedelta

import pytest

from kinetix.db.base import utcnow
from kinetix.db.models import PromoCode
from kinetix.errors import (
    PromoAlreadyUsed,
    PromoExhausted,
    PromoExpired,
    PromoNotFound,
)
from kinetix.services import orders, promo


async def make_promo(session, **kwargs) -> PromoCode:
    defaults = dict(code="SALE", percent=20, max_uses=0, per_user_limit=1)
    code = PromoCode(**{**defaults, **kwargs})
    session.add(code)
    await session.commit()
    return code


async def test_promo_discounts_the_order(db, session, factory):
    user = await factory.user(balance=10_000)
    product = await factory.product(price=1000, stock=10)
    await make_promo(session, percent=25)

    result = await orders.purchase(
        session,
        dialect=db.dialect,
        user_id=user.id,
        product_id=product.id,
        quantity=4,
        promo_code="sale",  # case-insensitive
    )

    assert result.total == 3000  # 4000 - 25%
    assert result.balance_after == 7000


async def test_promo_is_single_use_per_user(db, session, factory):
    user = await factory.user(balance=100_000)
    product = await factory.product(price=1000, stock=10)
    await make_promo(session, per_user_limit=1)
    user_id, product_id = user.id, product.id

    await orders.purchase(
        session,
        dialect=db.dialect,
        user_id=user_id,
        product_id=product_id,
        quantity=1,
        promo_code="SALE",
    )
    with pytest.raises(PromoAlreadyUsed):
        await orders.purchase(
            session,
            dialect=db.dialect,
            user_id=user_id,
            product_id=product_id,
            quantity=1,
            promo_code="SALE",
        )


async def test_unknown_inactive_and_expired_codes(db, session, factory):
    user = await factory.user()
    with pytest.raises(PromoNotFound):
        await promo.validate(session, "NOPE", user.id)

    await make_promo(session, code="OFF", is_active=False)
    with pytest.raises(PromoNotFound):
        await promo.validate(session, "OFF", user.id)

    await make_promo(session, code="OLD", expires_at=utcnow() - timedelta(days=1))
    with pytest.raises(PromoExpired):
        await promo.validate(session, "OLD", user.id)


async def test_global_use_limit(db, session, factory):
    code = await make_promo(session, max_uses=2, per_user_limit=0)
    user = await factory.user()

    for _ in range(2):
        validated = await promo.validate(session, "SALE", user.id)
        await promo.redeem(session, validated, user.id)
    await session.commit()

    assert code.used_count == 2
    with pytest.raises(PromoExhausted):
        await promo.validate(session, "SALE", user.id)
