"""Money helpers.

All amounts are stored and passed around as **integer minor units**
(kopecks / cents). Floats are never used for money.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MINOR_UNITS = 100

SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€", "UAH": "₴", "KZT": "₸"}

_AMOUNT_RE = re.compile(r"^\s*-?\d{1,12}([.,]\d{1,2})?\s*$")


class MoneyError(ValueError):
    """Raised when a user-supplied amount cannot be parsed."""


def parse_amount(raw: str) -> int:
    """Parse a human amount ("10", "10.50", "10,5") into minor units."""
    if not _AMOUNT_RE.match(raw or ""):
        raise MoneyError("invalid amount")
    try:
        value = Decimal(raw.strip().replace(",", "."))
    except InvalidOperation as exc:  # pragma: no cover - guarded by regex
        raise MoneyError("invalid amount") from exc
    minor = (value * MINOR_UNITS).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)


def to_decimal(minor: int) -> Decimal:
    return (Decimal(minor) / MINOR_UNITS).quantize(Decimal("0.01"))


def format_money(minor: int, currency: str = "RUB") -> str:
    """Render minor units for display: 12345 -> '123.45 ₽'."""
    symbol = SYMBOLS.get(currency.upper(), currency.upper())
    return f"{to_decimal(minor)} {symbol}"


def percent_of(minor: int, percent: int) -> int:
    """Integer percentage, rounded half-up. Used for referral payouts."""
    return int(
        (Decimal(minor) * Decimal(percent) / Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def apply_discount(minor: int, percent: int) -> int:
    """Subtract `percent` from `minor`, never dropping below zero."""
    discount = percent_of(minor, percent)
    return max(minor - discount, 0)
