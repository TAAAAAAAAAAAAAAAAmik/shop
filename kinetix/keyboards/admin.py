"""Inline keyboards for the admin panel."""

from __future__ import annotations

from collections.abc import Callable

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from kinetix.db.models import Product, TopUp
from kinetix.i18n import t
from kinetix.keyboards.callbacks import AdminCB, MenuCB, ReviewCB


def menu(locale: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(locale, "admin.btn.stats"), callback_data=AdminCB(action="stats"))
    kb.button(text=t(locale, "admin.btn.stock"), callback_data=AdminCB(action="stock"))
    kb.button(text=t(locale, "admin.btn.products"), callback_data=AdminCB(action="products"))
    kb.button(text=t(locale, "admin.btn.balance"), callback_data=AdminCB(action="balance"))
    kb.button(text=t(locale, "admin.btn.promo"), callback_data=AdminCB(action="promo"))
    kb.button(text=t(locale, "admin.btn.broadcast"), callback_data=AdminCB(action="broadcast"))
    kb.button(text=t(locale, "admin.btn.requests"), callback_data=AdminCB(action="requests"))
    kb.button(
        text=t(locale, "admin.btn.requisites"), callback_data=AdminCB(action="requisites")
    )
    kb.button(text=t(locale, "btn.menu"), callback_data=MenuCB(action="home"))
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()


def back(locale: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(locale, "btn.back"), callback_data=AdminCB(action="menu"))
    return kb.as_markup()


def pick_product(locale: str, items: list[Product], action: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for product in items:
        kb.button(
            text=f"#{product.id} {product.title(locale)}",
            callback_data=AdminCB(action=action, arg=product.id),
        )
    kb.button(text=t(locale, "btn.back"), callback_data=AdminCB(action="menu"))
    kb.adjust(1)
    return kb.as_markup()


def requests_list(
    locale: str, items: list[TopUp], label: Callable[[TopUp], str]
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for topup in items:
        kb.button(text=label(topup), callback_data=ReviewCB(topup_id=topup.id, action="open"))
    kb.button(text=t(locale, "btn.back"), callback_data=AdminCB(action="menu"))
    kb.adjust(1)
    return kb.as_markup()


def review_actions(locale: str, topup_id: int) -> InlineKeyboardMarkup:
    """Approve / reject, shown on the admin's review card."""
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(locale, "btn.approve"),
        callback_data=ReviewCB(topup_id=topup_id, action="approve"),
    )
    kb.button(
        text=t(locale, "btn.reject"), callback_data=ReviewCB(topup_id=topup_id, action="reject")
    )
    kb.button(text=t(locale, "admin.btn.requests"), callback_data=AdminCB(action="requests"))
    kb.adjust(2, 1)
    return kb.as_markup()
