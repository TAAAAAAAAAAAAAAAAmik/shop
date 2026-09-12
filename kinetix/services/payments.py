"""Settling CryptoBot invoices — on demand and from a background poller."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.config import Settings
from kinetix.db.base import Database
from kinetix.db.models import TopUp, TopUpStatus
from kinetix.errors import PaymentError
from kinetix.i18n import t
from kinetix.money import format_money
from kinetix.services import topups as topup_service
from kinetix.services.cryptobot import CryptoPay
from kinetix.services.topups import Credited

log = logging.getLogger(__name__)

PROVIDER = "cryptobot"


async def settle(
    session: AsyncSession,
    crypto: CryptoPay,
    topup: TopUp,
    settings: Settings,
    dialect: str,
) -> Credited | None:
    """Ask the provider about one invoice and credit it if it is paid."""
    invoices = await crypto.get_invoices([topup.external_id])
    if not invoices:
        return None

    invoice = invoices[0]
    if invoice.is_paid:
        return await topup_service.mark_paid(
            session,
            topup.id,
            dialect=dialect,
            referral_percent=settings.referral_percent,
        )
    if invoice.is_expired:
        await topup_service.mark_status(session, topup.id, TopUpStatus.EXPIRED)
    return None


async def announce_payer(
    bot: Bot, settings: Settings, credited: Credited, locale: str
) -> None:
    """Tell the payer their money landed."""
    try:
        await bot.send_message(
            credited.topup.user_id,
            t(
                locale,
                "balance.credited",
                amount=format_money(credited.topup.amount, settings.currency),
                balance=format_money(credited.balance_after, settings.currency),
            ),
        )
    except TelegramAPIError as exc:
        log.warning("could not notify payer %s: %s", credited.topup.user_id, exc)


async def announce_referrer(bot: Bot, settings: Settings, credited: Credited) -> None:
    """Tell the inviter about their cut. No-op when there is nothing to pay."""
    if not (credited.referrer_id and credited.referral_bonus):
        return
    try:
        referrer_locale = "ru"
        await bot.send_message(
            credited.referrer_id,
            t(
                referrer_locale,
                "balance.referral_bonus",
                amount=format_money(credited.referral_bonus, settings.currency),
                user=f"id{credited.topup.user_id}",
            ),
        )
    except TelegramAPIError as exc:
        log.warning("could not notify referrer %s: %s", credited.referrer_id, exc)


class PaymentPoller:
    """Polls pending invoices so no public webhook URL is needed.

    Swap this for a webhook (Crypto Pay signs updates with your app token) once
    the bot runs behind HTTPS; ``settle`` stays the same either way.
    """

    def __init__(self, db: Database, crypto: CryptoPay, bot: Bot, settings: Settings) -> None:
        self.db = db
        self.crypto = crypto
        self.bot = bot
        self.settings = settings
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="payment-poller")
            log.info("payment poller started (every %ss)", self.settings.payment_poll_interval)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # keep the loop alive through provider hiccups
                log.exception("payment poll failed")
            await asyncio.sleep(self.settings.payment_poll_interval)

    async def tick(self) -> int:
        """One sweep. Returns how many invoices were credited."""
        async with self.db.session() as session:
            await topup_service.expire_stale(session)
            pending = await topup_service.pending(session, PROVIDER)
            if not pending:
                return 0

            by_external = {topup.external_id: topup for topup in pending}
            try:
                invoices = await self.crypto.get_invoices(list(by_external))
            except PaymentError as exc:
                log.warning("crypto pay unavailable: %s", exc)
                return 0

            credited_count = 0
            for invoice in invoices:
                topup = by_external.get(invoice.invoice_id)
                if topup is None:
                    continue
                if invoice.is_expired:
                    await topup_service.mark_status(session, topup.id, TopUpStatus.EXPIRED)
                    continue
                if not invoice.is_paid:
                    continue

                credited = await topup_service.mark_paid(
                    session,
                    topup.id,
                    dialect=self.db.dialect,
                    referral_percent=self.settings.referral_percent,
                )
                if credited is None:
                    continue

                credited_count += 1
                locale = credited.topup.user.locale if credited.topup.user else "ru"
                await announce_payer(self.bot, self.settings, credited, locale)
                await announce_referrer(self.bot, self.settings, credited)

            return credited_count
