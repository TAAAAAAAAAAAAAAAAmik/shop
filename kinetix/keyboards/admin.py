"""Inline keyboards for the admin panel."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from kinetix.db.models import Product
from kinetix.i18n import t
from kinetix.keyboards.callbacks import AdminCB, MenuCB


def menu(locale: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(locale, "admin.btn.stats"), callback_data=AdminCB(action="stats"))
    kb.button(text=t(locale, "admin.btn.stock"), callback_data=AdminCB(action="stock"))
    kb.button(text=t(locale, "admin.btn.products"), callback_data=AdminCB(action="products"))
    kb.button(text=t(locale, "admin.btn.balance"), callback_data=AdminCB(action="balance"))
    kb.button(text=t(locale, "admin.btn.promo"), callback_data=AdminCB(action="promo"))
    kb.button(text=t(locale, "admin.btn.broadcast"), callback_data=AdminCB(action="broadcast"))
    kb.button(text=t(locale, "btn.menu"), callback_data=MenuCB(action="home"))
    kb.adjust(2, 2, 2, 1)
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
