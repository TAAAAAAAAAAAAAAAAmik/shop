"""Minimal async client for the Crypto Pay API (@CryptoBot).

Docs: https://help.crypt.bot/crypto-pay-api
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import aiohttp

from kinetix.errors import PaymentError
from kinetix.money import to_decimal

log = logging.getLogger(__name__)

MAINNET = "https://pay.crypt.bot/api"
TESTNET = "https://testnet-pay.crypt.bot/api"


@dataclass(slots=True)
class Invoice:
    invoice_id: str
    status: str
    pay_url: str
    amount: str
    payload: str | None = None

    @property
    def is_paid(self) -> bool:
        return self.status == "paid"

    @property
    def is_expired(self) -> bool:
        return self.status == "expired"


class CryptoPay:
    def __init__(self, token: str, *, testnet: bool = False, timeout: int = 20) -> None:
        self._token = token
        self._base = TESTNET if testnet else MAINNET
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _client(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout, headers={"Crypto-Pay-API-Token": self._token}
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _call(self, method: str, **params: Any) -> Any:
        session = await self._client()
        url = f"{self._base}/{method}"
        try:
            async with session.post(url, json=params) as response:
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise PaymentError(f"crypto pay request failed: {exc}") from exc

        if not isinstance(body, dict) or not body.get("ok"):
            error = body.get("error") if isinstance(body, dict) else body
            raise PaymentError(f"crypto pay error: {error}")
        return body["result"]

    async def get_me(self) -> dict[str, Any]:
        return await self._call("getMe")

    async def create_invoice(
        self,
        *,
        amount_minor: int,
        fiat: str,
        description: str,
        payload: str,
        expires_in: int = 3600,
    ) -> Invoice:
        """Create a fiat-denominated invoice; the payer picks the crypto asset."""
        result = await self._call(
            "createInvoice",
            currency_type="fiat",
            fiat=fiat.upper(),
            amount=str(to_decimal(amount_minor)),
            description=description[:1024],
            payload=payload[:4096],
            expires_in=expires_in,
            allow_comments=False,
            allow_anonymous=True,
        )
        return _parse_invoice(result)

    async def get_invoices(self, invoice_ids: list[str]) -> list[Invoice]:
        if not invoice_ids:
            return []
        result = await self._call(
            "getInvoices", invoice_ids=",".join(invoice_ids), count=len(invoice_ids)
        )
        items = result.get("items", []) if isinstance(result, dict) else result
        return [_parse_invoice(item) for item in items]

    async def delete_invoice(self, invoice_id: str) -> bool:
        try:
            return bool(await self._call("deleteInvoice", invoice_id=int(invoice_id)))
        except PaymentError:
            log.warning("could not delete invoice %s", invoice_id)
            return False


def _parse_invoice(raw: dict[str, Any]) -> Invoice:
    return Invoice(
        invoice_id=str(raw.get("invoice_id")),
        status=str(raw.get("status", "")),
        pay_url=str(raw.get("bot_invoice_url") or raw.get("pay_url") or ""),
        amount=str(raw.get("amount") or Decimal(0)),
        payload=raw.get("payload"),
    )
