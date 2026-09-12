"""ORM models.

Money is stored everywhere as integer minor units (see ``kinetix.money``).
Every balance change is mirrored into ``BalanceTx`` so the wallet is auditable.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kinetix.db.base import Base, TimestampMixin, utcnow


class TopUpStatus(enum.StrEnum):
    PENDING = "pending"
    # Manual transfers only: the payer says they sent the money, staff verify it.
    AWAITING_REVIEW = "awaiting_review"
    PAID = "paid"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @property
    def is_open(self) -> bool:
        """Still occupying the user's single open top-up slot."""
        return self in {TopUpStatus.PENDING, TopUpStatus.AWAITING_REVIEW}


class TxKind(enum.StrEnum):
    TOPUP = "topup"
    PURCHASE = "purchase"
    REFERRAL = "referral"
    ADMIN = "admin"
    REFUND = "refund"


def _enum(python_enum: type[enum.Enum], name: str) -> Enum:
    """Portable enum column: stored as VARCHAR, validated in Python."""
    return Enum(
        python_enum,
        name=name,
        native_enum=False,
        values_callable=lambda e: [member.value for member in e],
        length=20,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    locale: Mapped[str] = mapped_column(String(2), default="ru", nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referrer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    total_spent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    referrals: Mapped[list[User]] = relationship(remote_side=[referrer_id], viewonly=True)
    orders: Mapped[list[Order]] = relationship(back_populates="user", lazy="noload")

    @property
    def mention(self) -> str:
        return f"@{self.username}" if self.username else f"id{self.id}"


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_ru: Mapped[str] = mapped_column(String(128), nullable=False)
    title_en: Mapped[str] = mapped_column(String(128), nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), default="📦", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    products: Mapped[list[Product]] = relationship(
        back_populates="category", cascade="all, delete-orphan", lazy="noload"
    )

    def title(self, locale: str) -> str:
        return self.title_en if locale == "en" else self.title_ru


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title_ru: Mapped[str] = mapped_column(String(128), nullable=False)
    title_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description_ru: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_per_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped[Category] = relationship(back_populates="products", lazy="selectin")
    tiers: Mapped[list[PriceTier]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PriceTier.min_qty",
    )

    def title(self, locale: str) -> str:
        return self.title_en if locale == "en" else self.title_ru

    def description(self, locale: str) -> str:
        return self.description_en if locale == "en" else self.description_ru

    def unit_price(self, quantity: int) -> int:
        """Bulk pricing: the cheapest tier whose threshold the order reaches."""
        price = self.price
        for tier in sorted(self.tiers, key=lambda t: t.min_qty):
            if quantity >= tier.min_qty:
                price = tier.price
        return price


class PriceTier(Base):
    __tablename__ = "price_tiers"
    __table_args__ = (UniqueConstraint("product_id", "min_qty"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)

    product: Mapped[Product] = relationship(back_populates="tiers")


class StockItem(Base, TimestampMixin):
    """One deliverable unit: a key, a link, a code."""

    __tablename__ = "stock_items"
    __table_args__ = (
        Index("ix_stock_available", "product_id", "is_sold"),
        UniqueConstraint("product_id", "payload", name="uq_stock_product_payload"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(lazy="selectin")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promo_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(back_populates="orders", lazy="selectin")
    product: Mapped[Product] = relationship(lazy="selectin")
    items: Mapped[list[StockItem]] = relationship(
        primaryjoin="Order.id == StockItem.order_id", lazy="selectin", viewonly=True
    )


class TopUp(Base, TimestampMixin):
    __tablename__ = "topups"
    __table_args__ = (UniqueConstraint("provider", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[TopUpStatus] = mapped_column(
        _enum(TopUpStatus, "topup_status"), default=TopUpStatus.PENDING, nullable=False, index=True
    )
    pay_url: Mapped[str | None] = mapped_column(String(512))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Manual review trail
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="selectin")


class Setting(Base):
    """Small key/value store for values staff edit at runtime (bank details)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PromoCode(Base, TimestampMixin):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = unlimited
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PromoUse(Base, TimestampMixin):
    __tablename__ = "promo_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_code_id: Mapped[int] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))


class BalanceTx(Base, TimestampMixin):
    """Append-only ledger of every balance movement."""

    __tablename__ = "balance_txs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # signed
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[TxKind] = mapped_column(_enum(TxKind, "tx_kind"), nullable=False)
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    comment: Mapped[str] = mapped_column(String(256), default="", nullable=False)
