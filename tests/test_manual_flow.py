"""End-to-end manual transfer: request → "I paid" → staff approve/reject."""

from __future__ import annotations

from sqlalchemy import select

from kinetix.config import Settings
from kinetix.db.models import TopUp, TopUpStatus, User
from kinetix.keyboards.callbacks import MenuCB, PayCB, ReviewCB, TopUpCB
from tests.conftest import REQUISITES
from tests.updates import ADMIN_ID, CUSTOMER_ID
from tests.updates import callback_update as _callback
from tests.updates import message_update as _message


def sent_to(session, chat_id: int) -> str:
    """Everything the bot sent to one chat, joined."""
    return "\n".join(
        (getattr(call, "text", "") or "")
        for call in session.calls
        if str(getattr(call, "chat_id", "")) == str(chat_id)
    )


async def open_request(dp, bot, db, amount: str = "500", start_at: int = 1) -> TopUp:
    """Drive the customer UI up to a created (not yet claimed) request."""
    await dp.feed_update(bot, _message("/start", update_id=start_at))
    await dp.feed_update(bot, _callback(MenuCB(action="topup").pack(), update_id=start_at + 1))
    await dp.feed_update(
        bot, _callback(PayCB(method="manual").pack(), update_id=start_at + 2)
    )
    await dp.feed_update(bot, _message(amount, update_id=start_at + 3))
    async with db.session() as s:
        return (await s.execute(select(TopUp))).scalars().all()[-1]


async def test_method_picker_offers_bank_transfer(app, db):
    dp, bot, session = app
    await dp.feed_update(bot, _message("/start"))
    await dp.feed_update(bot, _callback(MenuCB(action="topup").pack(), update_id=2))

    buttons = [
        button.text
        for call in session.calls
        if getattr(call, "reply_markup", None)
        for row in call.reply_markup.inline_keyboard
        for button in row
    ]
    assert any("Перевод" in text for text in buttons)
    # CryptoBot is not configured in tests, so it must not be offered.
    assert not any("CryptoBot" in text for text in buttons)


async def test_requisites_and_reference_are_shown(app, db):
    dp, bot, session = app
    topup = await open_request(dp, bot, db)

    assert topup.amount == 50_000
    assert topup.status is TopUpStatus.PENDING
    assert "2202 2020 1111 2222" in session.last_text
    assert topup.external_id in session.last_text


async def test_claim_notifies_staff_and_queues_review(app, db):
    dp, bot, session = app
    topup = await open_request(dp, bot, db)

    await dp.feed_update(
        bot, _callback(TopUpCB(topup_id=topup.id, action="paid").pack(), update_id=10)
    )

    async with db.session() as s:
        stored = await s.get(TopUp, topup.id)
        assert stored.status is TopUpStatus.AWAITING_REVIEW
        assert stored.submitted_at is not None

    assert "на проверку" in sent_to(session, CUSTOMER_ID)
    staff_message = sent_to(session, ADMIN_ID)
    assert "Новая заявка" in staff_message
    assert topup.external_id in staff_message


async def test_approval_credits_and_tells_the_payer(app, db):
    dp, bot, session = app
    topup = await open_request(dp, bot, db)
    await dp.feed_update(
        bot, _callback(TopUpCB(topup_id=topup.id, action="paid").pack(), update_id=10)
    )

    await dp.feed_update(
        bot,
        _callback(
            ReviewCB(topup_id=topup.id, action="approve").pack(),
            user_id=ADMIN_ID,
            update_id=11,
        ),
    )

    async with db.session() as s:
        assert (await s.get(User, CUSTOMER_ID)).balance == 50_000
        stored = await s.get(TopUp, topup.id)
        assert stored.status is TopUpStatus.PAID
        assert stored.reviewed_by == ADMIN_ID

    assert "подтверждена" in sent_to(session, CUSTOMER_ID)


async def test_second_approval_is_refused(app, db):
    dp, bot, session = app
    topup = await open_request(dp, bot, db)
    await dp.feed_update(
        bot, _callback(TopUpCB(topup_id=topup.id, action="paid").pack(), update_id=10)
    )
    approve = ReviewCB(topup_id=topup.id, action="approve").pack()

    await dp.feed_update(bot, _callback(approve, user_id=ADMIN_ID, update_id=11))
    await dp.feed_update(bot, _callback(approve, user_id=ADMIN_ID, update_id=12))

    assert "уже обработана" in session.last_text
    async with db.session() as s:
        assert (await s.get(User, CUSTOMER_ID)).balance == 50_000  # credited once


async def test_rejection_credits_nothing(app, db):
    dp, bot, session = app
    topup = await open_request(dp, bot, db)
    await dp.feed_update(
        bot, _callback(TopUpCB(topup_id=topup.id, action="paid").pack(), update_id=10)
    )

    await dp.feed_update(
        bot,
        _callback(
            ReviewCB(topup_id=topup.id, action="reject").pack(),
            user_id=ADMIN_ID,
            update_id=11,
        ),
    )

    async with db.session() as s:
        assert (await s.get(User, CUSTOMER_ID)).balance == 0
        assert (await s.get(TopUp, topup.id)).status is TopUpStatus.REJECTED
    assert "отклонена" in sent_to(session, CUSTOMER_ID)


async def test_only_one_open_request_at_a_time(app, db):
    """Picking "bank transfer" again re-shows the open request, never a second one."""
    dp, bot, session = app
    first = await open_request(dp, bot, db, amount="500")

    await dp.feed_update(bot, _callback(PayCB(method="manual").pack(), update_id=20))

    assert first.external_id in session.last_text
    assert "Введите сумму" not in session.last_text
    async with db.session() as s:
        assert len((await s.execute(select(TopUp))).scalars().all()) == 1


async def test_cancel_frees_the_slot(app, db):
    dp, bot, session = app
    topup = await open_request(dp, bot, db)

    await dp.feed_update(
        bot, _callback(TopUpCB(topup_id=topup.id, action="cancel").pack(), update_id=10)
    )
    assert "отменена" in session.last_text.lower()

    await dp.feed_update(bot, _callback(PayCB(method="manual").pack(), update_id=11))
    assert "Введите сумму" in session.last_text


async def test_amount_outside_limits_is_refused(app, db):
    dp, bot, session = app
    await dp.feed_update(bot, _message("/start", update_id=1))
    await dp.feed_update(bot, _callback(PayCB(method="manual").pack(), update_id=2))
    await dp.feed_update(bot, _message("1", update_id=3))  # below MIN_TOPUP

    assert "должна быть от" in session.last_text
    async with db.session() as s:
        assert (await s.execute(select(TopUp))).scalars().all() == []


async def test_no_methods_when_nothing_is_configured(app, db, settings):
    dp, bot, session = app
    dp["settings"] = Settings(
        _env_file=None,
        BOT_TOKEN=settings.bot_token,
        ADMIN_IDS=str(ADMIN_ID),
        THROTTLE_RATE=0,
        MANUAL_PAYMENT_ENABLED=False,
        CRYPTO_PAY_TOKEN="",
        SUPPORT_USERNAME="kinetix_support",
    )

    await dp.feed_update(bot, _message("/start", update_id=1))
    await dp.feed_update(bot, _callback(MenuCB(action="topup").pack(), update_id=2))

    assert "временно недоступно" in session.last_text
    assert "@kinetix_support" in session.last_text


async def test_requisites_can_be_edited_by_staff(app, db):
    dp, bot, session = app
    await dp.feed_update(bot, _message("/admin", user_id=ADMIN_ID, update_id=1))
    await dp.feed_update(
        bot, _callback("a:requisites:0", user_id=ADMIN_ID, update_id=2)
    )
    assert REQUISITES.splitlines()[0] in session.last_text

    await dp.feed_update(
        bot, _message("Т-Банк 5536 9138 0000 1111", user_id=ADMIN_ID, update_id=3)
    )
    assert "обновлены" in session.last_text

    topup = await open_request(dp, bot, db, start_at=10)
    assert "5536 9138 0000 1111" in session.last_text
    assert topup.status is TopUpStatus.PENDING
