"""Domain errors. Handlers translate these into user-facing messages."""

from __future__ import annotations


class ShopError(Exception):
    """Base class for expected, user-visible failures."""


class InsufficientFunds(ShopError):
    def __init__(self, missing: int) -> None:
        super().__init__(f"missing {missing}")
        self.missing = missing


class OutOfStock(ShopError):
    def __init__(self, available: int) -> None:
        super().__init__(f"only {available} left")
        self.available = available


class ProductUnavailable(ShopError):
    pass


class InvalidQuantity(ShopError):
    pass


class PromoError(ShopError):
    """Base for promo-code rejections; `reason` keys a locale string."""

    reason = "invalid"


class PromoNotFound(PromoError):
    reason = "not_found"


class PromoExpired(PromoError):
    reason = "expired"


class PromoExhausted(PromoError):
    reason = "exhausted"


class PromoAlreadyUsed(PromoError):
    reason = "already_used"


class PaymentError(ShopError):
    pass
