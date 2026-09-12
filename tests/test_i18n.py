from kinetix.i18n import LOCALES, normalize_locale, t


def test_locales_have_identical_keys():
    ru, en = LOCALES["ru"], LOCALES["en"]
    assert set(ru) == set(en), f"drift: {set(ru) ^ set(en)}"


def test_placeholders_match_between_locales():
    import string

    def fields(template: str) -> set[str]:
        return {f for _, f, _, _ in string.Formatter().parse(template) if f}

    for key, ru_text in LOCALES["ru"].items():
        assert fields(ru_text) == fields(LOCALES["en"][key]), key


def test_translation_and_fallbacks():
    assert t("ru", "btn.back") == "◀️ Назад"
    assert t("en", "btn.back") == "◀️ Back"
    assert t("de", "btn.back") == "◀️ Назад"  # unknown locale -> default
    assert t("ru", "no.such.key") == "no.such.key"
    assert "500" in t("ru", "balance.out_of_range", min="500", max="1000")


def test_missing_format_args_do_not_crash():
    assert t("ru", "menu.title", shop="Kinetix")  # 'balance' missing, must not raise


def test_normalize_locale():
    assert normalize_locale("ru-RU") == "ru"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("fr") == "en"
    assert normalize_locale(None) == "ru"
