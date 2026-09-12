"""FSM states."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BuyFlow(StatesGroup):
    quantity = State()
    promo = State()


class TopUpFlow(StatesGroup):
    amount = State()


class AdminFlow(StatesGroup):
    stock_payload = State()
    balance_user = State()
    balance_amount = State()
    promo_spec = State()
    broadcast_message = State()
