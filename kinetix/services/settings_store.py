"""Runtime-editable settings, so staff can change bank details without a redeploy."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kinetix.db.models import Setting

MANUAL_REQUISITES = "manual_requisites"


async def get(session: AsyncSession, key: str, default: str = "") -> str:
    row = await session.get(Setting, key)
    return row.value if row is not None and row.value else default


async def set_value(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def requisites(session: AsyncSession, fallback: str = "") -> str:
    """Bank details shown to a payer, falling back to the env-configured value."""
    return await get(session, MANUAL_REQUISITES, fallback)
