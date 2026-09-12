import pytest
from pydantic import ValidationError

from kinetix.config import Settings

# _env_file=None so a developer's local .env can never leak into these assertions.
BASE = {"BOT_TOKEN": "1:x", "_env_file": None}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("123", [123]),
        (123, [123]),  # pydantic-settings JSON-decodes a lone number
        ("1,2,3", [1, 2, 3]),
        ("1; 2 ;3", [1, 2, 3]),
        ([7, 8], [7, 8]),
        ("", []),
    ],
)
def test_admin_ids_parsing(raw, expected):
    assert Settings(**BASE, ADMIN_IDS=raw).admin_ids == expected


def test_is_admin():
    settings = Settings(**BASE, ADMIN_IDS="5,6")
    assert settings.is_admin(5)
    assert not settings.is_admin(7)


def test_crypto_pay_toggle():
    assert not Settings(**BASE).crypto_pay_enabled
    assert Settings(**BASE, CRYPTO_PAY_TOKEN="tok").crypto_pay_enabled


def test_referral_percent_bounds():
    assert Settings(**BASE, REFERRAL_PERCENT=0).referral_percent == 0
    with pytest.raises(ValidationError):
        Settings(**BASE, REFERRAL_PERCENT=101)


def test_bot_token_is_required():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ADMIN_IDS="1")
