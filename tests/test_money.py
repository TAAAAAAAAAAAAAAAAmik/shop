import pytest

from kinetix.money import (
    MoneyError,
    apply_discount,
    format_money,
    parse_amount,
    percent_of,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("10", 1000), ("10.5", 1050), ("10,55", 1055), ("0.01", 1), (" 250 ", 25000)],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "10.999", "1e5", "--5", "10.5.5"])
def test_parse_amount_rejects_garbage(raw):
    with pytest.raises(MoneyError):
        parse_amount(raw)


def test_format_money():
    assert format_money(123456, "RUB") == "1234.56 ₽"
    assert format_money(0, "USD") == "0.00 $"


def test_percent_rounds_half_up():
    assert percent_of(1005, 5) == 50  # 50.25 -> 50
    assert percent_of(1010, 5) == 51  # 50.50 -> 51


def test_discount_never_negative():
    assert apply_discount(1000, 30) == 700
    assert apply_discount(1000, 100) == 0
    assert apply_discount(1000, 150) == 0
