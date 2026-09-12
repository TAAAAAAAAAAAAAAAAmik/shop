"""Inline keyboards for the customer-facing flows."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from kinetix.db.models import Category, Product
from kinetix.i18n import LOCALE_NAMES, t
from kinetix.keyboards.callbacks import (
    AdminCB,
    BuyCB,
    CategoryCB,
    LangCB,
    MenuCB,
    PayCB,
    ProductCB,
    TopUpCB,
)


def main_menu(locale: str, *, is_admin: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(locale, "menu.catalog"), callback_data=MenuCB(action="catalog"))
    kb.button(text=t(locale, "menu.topup"), callback_data=MenuCB(action="topup"))
    kb.button(text=t(locale, "menu.profile"), callback_data=MenuCB(action="profile"))
    kb.button(text=t(locale, "menu.orders"), callback_data=MenuCB(action="orders"))
    kb.button(text=t(locale, "menu.referral"), callback_data=MenuCB(action="referral"))
    kb.button(text=t(locale, "menu.support"), callback_data=MenuCB(action="support"))
    kb.button(text=t(locale, "menu.language"), callback_data=MenuCB(action="lang"))
    if is_admin:
        kb.button(text=t(locale, "menu.admin"), callback_data=AdminCB(action="menu"))
    kb.adjust(1, 1, 2, 2, 1, 1)
    return kb.as_markup()


def back_to(locale: str, action: str = "home") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(locale, "btn.back"), callback_data=MenuCB(action=action))
    return kb.as_markup()


def categories(locale: str, items: list[Category]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for category in items:
        kb.button(
            text=f"{category.emoji} {category.title(locale)}",
            callback_data=CategoryCB(category_id=category.id),
        )
    kb.button(text=t(locale, "btn.back"), callback_data=MenuCB(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def products(
    locale: str, items: list[Product], stock: dict[int, int], currency: str
) -> InlineKeyboardMarkup:
    from kinetix.money import format_money

    kb = InlineKeyboardBuilder()
    for product in items:
        left = stock.get(product.id, 0)
        mark = "" if left else "❌ "
        kb.button(
            text=f"{mark}{product.title(locale)} — {format_money(product.price, currency)}",
            callback_data=ProductCB(product_id=product.id),
        )
    kb.button(text=t(locale, "btn.back"), callback_data=MenuCB(action="catalog"))
    kb.adjust(1)
    return kb.as_markup()


def product_card(
    locale: str, product: Product, *, in_stock: bool, has_promo: bool
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if in_stock:
        kb.button(
            text=t(locale, "btn.buy"),
            callback_data=BuyCB(product_id=product.id, action="start"),
        )
    kb.button(
        text=t(locale, "btn.promo_clear" if has_promo else "btn.promo"),
        callback_data=BuyCB(product_id=product.id, action="clear" if has_promo else "promo"),
    )
    kb.button(
        text=t(locale, "btn.back"), callback_data=CategoryCB(category_id=product.category_id)
    )
    kb.adjust(1)
    return kb.as_markup()


def confirm_order(locale: str, product_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(locale, "btn.confirm"),
        callback_data=BuyCB(product_id=product_id, action="confirm"),
    )
    kb.button(text=t(locale, "btn.cancel"), callback_data=ProductCB(product_id=product_id))
    kb.adjust(1)
    return kb.as_markup()


def invoice(locale: str, topup_id: int, pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(locale, "btn.pay"), url=pay_url)],
            [
                InlineKeyboardButton(
                    text=t(locale, "btn.check"),
                    callback_data=TopUpCB(topup_id=topup_id, action="check").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(locale, "btn.menu"), callback_data=MenuCB(action="home").pack()
                )
            ],
        ]
    )


def languages(locale: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, name in LOCALE_NAMES.items():
        kb.button(text=name, callback_data=LangCB(code=code))
    kb.button(text=t(locale, "btn.back"), callback_data=MenuCB(action="home"))
    kb.adjust(2, 1)
    return kb.as_markup()


def topup_methods(locale: str, *, crypto: bool, manual: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if crypto:
        kb.button(text=t(locale, "btn.method_crypto"), callback_data=PayCB(method="crypto"))
    if manual:
        kb.button(text=t(locale, "btn.method_manual"), callback_data=PayCB(method="manual"))
    kb.button(text=t(locale, "btn.back"), callback_data=MenuCB(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def manual_request(locale: str, topup_id: int, *, claimable: bool) -> InlineKeyboardMarkup:
    """Buttons under a manual transfer request."""
    kb = InlineKeyboardBuilder()
    if claimable:
        kb.button(
            text=t(locale, "btn.paid"), callback_data=TopUpCB(topup_id=topup_id, action="paid")
        )
        kb.button(
            text=t(locale, "btn.cancel"),
            callback_data=TopUpCB(topup_id=topup_id, action="cancel"),
        )
    kb.button(text=t(locale, "btn.menu"), callback_data=MenuCB(action="home"))
    kb.adjust(1)
    return kb.as_markup()
