import sys
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

I18N = WB / "extension" / "lib" / "i18n"


def test_registry_and_english_baseline():
    locales = (I18N / "locales.js").read_text(encoding="utf-8")
    assert 'BASE_LOCALE = "en"' in locales
    assert 'fallback: "en"' in locales


def test_index_uses_registry_and_readable_fallback():
    index = (I18N / "index.js").read_text(encoding="utf-8")
    assert "locales.js" in index
    assert "BASE_LOCALE" in index
    assert "[${key}]" not in index
    assert "Text unavailable" in index
    assert "chain.length < 2" in index


def test_locale_files_have_same_keys():
    sys.path.insert(0, str(WB / "tools"))
    from check_i18n_wb import entries  # noqa: E402

    zh = entries(I18N / "zh.js")
    en = entries(I18N / "en.js")
    assert set(zh) == set(en)