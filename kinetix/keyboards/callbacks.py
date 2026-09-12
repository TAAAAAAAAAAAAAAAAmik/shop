"""Typed callback payloads shared by keyboards and handlers."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="m"):
    action: str  # home | catalog | profile | topup | orders | referral | support | lang | admin


class CategoryCB(CallbackData, prefix="cat"):
    category_id: int


class ProductCB(CallbackData, prefix="p"):
    product_id: int


class BuyCB(CallbackData, prefix="buy"):
    product_id: int
    action: str  # start | confirm | promo | clear


class LangCB(CallbackData, prefix="lang"):
    code: str


class TopUpCB(CallbackData, prefix="top"):
    topup_id: int
    action: str  # check | cancel


class AdminCB(CallbackData, prefix="a"):
    action: str
    arg: int = 0


class PayCB(CallbackData, prefix="pay"):
    method: str  # crypto | manual


class ReviewCB(CallbackData, prefix="rev"):
    topup_id: int
    action: str  # open | approve | reject
