"""Tiny dictionary-based translator (RU/EN)."""

from __future__ import annotations

import logging

from kinetix.locales import en, ru

log = logging.getLogger(__name__)

LOCALES: dict[str, dict[str, str]] = {"ru": ru.TEXTS, "en": en.TEXTS}
DEFAULT_LOCALE = "ru"

LOCALE_NAMES = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English"}


def normalize_locale(code: str | None) -> str:
    """Map a Telegram language code onto a locale we actually ship."""
    if not code:
        return DEFAULT_LOCALE
    return code.split("-")[0].lower() if code.split("-")[0].lower() in LOCALES else "en"


def t(locale: str, key: str, /, **kwargs: object) -> str:
    """Translate `key`, falling back to the default locale and then the key itself."""
    texts = LOCALES.get(locale) or LOCALES[DEFAULT_LOCALE]
    template = texts.get(key) or LOCALES[DEFAULT_LOCALE].get(key)
    if template is None:
        log.warning("missing translation key: %s", key)
        return key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        log.warning("bad format args for key %s: %s", key, sorted(kwargs))
        return template
