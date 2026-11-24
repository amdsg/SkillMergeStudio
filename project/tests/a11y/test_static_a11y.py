from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


def _css_files():
    return sorted((WEB / "css").glob("*.css"))


def test_no_outline_none_anywhere():
    for path in _css_files():
        text = path.read_text(encoding="utf-8").replace(" ", "").lower()
        assert "outline:none" not in text, f"{path} 禁止 outline:none"


def test_focus_visible_rule_exists():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in _css_files())
    assert ":focus-visible" in combined


def test_html_buttons_declare_type():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for match in re.finditer(r"<button\b[^>]*>", html):
        assert "type=" in match.group(0), match.group(0)


def test_key_regions_have_aria_labels():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for marker in ('id="list"', 'id="detail"', 'id="preview-modal"', 'id="history-modal"', 'id="settings-modal"'):
        assert marker in html
    assert "aria-label" in html
    assert "aria-modal=\"true\"" in html


def test_html_declares_language_toggle():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'id="lang-select"' in html
    assert 'value="zh"' in html and 'value="en"' in html
    assert "data-i18n=" in html