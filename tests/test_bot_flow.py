"""End-to-end: real updates through the real dispatcher, fake Telegram."""

from __future__ import annotations

from sqlalchemy import func, select

from kinetix.db.models import Order, StockItem, User
from kinetix.keyboards.callbacks import BuyCB, CategoryCB, MenuCB, ProductCB
from tests.mocked_bot import BOT_USERNAME
from tests.updates import ADMIN_ID, CUSTOMER_ID
from tests.updates import callback_update as _callback
from tests.updates import message_update as _message


async def test_start_registers_user_and_shows_menu(app, db):
    dp, bot, session = app

    await dp.feed_update(bot, _message("/start"))

    assert "Kinetix" in session.last_text
    async with db.session() as s:
        user = await s.get(User, CUSTOMER_ID)
        assert user is not None
        assert user.username == f"user{CUSTOMER_ID}"


async def test_deep_link_records_referrer(app, db):
    dp, bot, session = app

    await dp.feed_update(bot, _message("/start", user_id=ADMIN_ID, update_id=1))
    await dp.feed_update(bot, _message(f"/start {ADMIN_ID}", update_id=2))

    async with db.session() as s:
        invited = await s.get(User, CUSTOMER_ID)
        assert invited.referrer_id == ADMIN_ID


async def test_referral_link_is_rendered(app):
    dp, bot, session = app
    await dp.feed_update(bot, _message("/start"))
    await dp.feed_update(bot, _callback(MenuCB(action="referral").pack(), update_id=2))

    assert f"https://t.me/{BOT_USERNAME}?start={CUSTOMER_ID}" in session.last_text


async def test_empty_catalog_is_handled(app):
    dp, bot, session = app
    await dp.feed_update(bot, _message("/start"))
    await dp.feed_update(bot, _callback(MenuCB(action="catalog").pack(), update_id=2))

    assert "пуст" in session.last_text.lower()


async def test_full_purchase_journey(app, db, factory):
    """Browse → pick → quantity → confirm → goods delivered, balance charged."""
    dp, bot, session = app

    product = await factory.product(price=10_000, stock=5)
    async with db.session() as s:
        s.add(User(id=CUSTOMER_ID, username="buyer", balance=100_000))
        await s.commit()

    await dp.feed_update(bot, _message("/start", update_id=1))
    await dp.feed_update(bot, _callback(MenuCB(action="catalog").pack(), update_id=2))
    await dp.feed_update(
        bot, _callback(CategoryCB(category_id=product.category_id).pack(), update_id=3)
    )
    await dp.feed_update(bot, _callback(ProductCB(product_id=product.id).pack(), update_id=4))
    assert "В наличии" in session.last_text

    await dp.feed_update(
        bot, _callback(BuyCB(product_id=product.id, action="start").pack(), update_id=5)
    )
    await dp.feed_update(bot, _message("3", update_id=6))
    assert "Итого" in session.last_text

    await dp.feed_update(
        bot, _callback(BuyCB(product_id=product.id, action="confirm").pack(), update_id=7)
    )

    async with db.session() as s:
        order = (await s.execute(select(Order))).scalar_one()
        assert order.quantity == 3
        assert order.total == 30_000

        buyer = await s.get(User, CUSTOMER_ID)
        assert buyer.balance == 70_000
        assert buyer.total_spent == 30_000

        sold = (
            await s.execute(
                select(func.count()).select_from(StockItem).where(StockItem.is_sold.is_(True))
            )
        ).scalar_one()
        assert sold == 3

    delivered = "\n".join(session.texts())
    assert "KEY-0000" in delivered and "KEY-0002" in delivered


async def test_purchase_without_funds_is_refused(app, db, factory):
    dp, bot, session = app
    product = await factory.product(price=10_000, stock=5)
    async with db.session() as s:
        s.add(User(id=CUSTOMER_ID, username="broke", balance=100))
        await s.commit()

    await dp.feed_update(bot, _message("/start", update_id=1))
    await dp.feed_update(
        bot, _callback(BuyCB(product_id=product.id, action="start").pack(), update_id=2)
    )
    await dp.feed_update(bot, _message("1", update_id=3))
    await dp.feed_update(
        bot, _callback(BuyCB(product_id=product.id, action="confirm").pack(), update_id=4)
    )

    assert "Недостаточно средств" in session.last_text
    async with db.session() as s:
        assert (await s.get(User, CUSTOMER_ID)).balance == 100
        assert (await s.execute(select(func.count()).select_from(Order))).scalar_one() == 0


async def test_admin_panel_is_gated(app, db):
    dp, bot, session = app

    await dp.feed_update(bot, _message("/admin", user_id=CUSTOMER_ID, update_id=1))
    customer_calls = len(session.calls)

    await dp.feed_update(bot, _message("/admin", user_id=ADMIN_ID, update_id=2))
    assert "Админка" in session.last_text
    assert len(session.calls) > customer_calls


async def test_banned_user_is_stopped(app, db):
    dp, bot, session = app
    async with db.session() as s:
        s.add(User(id=CUSTOMER_ID, username="banned", is_banned=True))
        await s.commit()

    await dp.feed_update(bot, _message("/start"))
    assert "ограничен" in session.last_text


async def test_language_switch_persists(app, db):
    dp, bot, session = app
    await dp.feed_update(bot, _message("/start", update_id=1))
    await dp.feed_update(bot, _callback("lang:en", update_id=2))

    assert "Catalogue" in "\n".join(
        button.text
        for call in session.calls
        if getattr(call, "reply_markup", None)
        for row in call.reply_markup.inline_keyboard
        for button in row
    )
    async with db.session() as s:
        assert (await s.get(User, CUSTOMER_ID)).locale == "en"
