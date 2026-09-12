"""Admin routers, gated behind :class:`IsAdmin`."""

from __future__ import annotations

from aiogram import Router

from kinetix.handlers.admin import ops, panel, requests, stock
from kinetix.handlers.admin.filters import IsAdmin


def build_router() -> Router:
    router = Router(name="admin")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())
    router.include_routers(panel.router, stock.router, ops.router, requests.router)
    return router
