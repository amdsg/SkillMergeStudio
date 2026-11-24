from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path):
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _i18n_keys(text):
    return set(re.findall(r'"([a-zA-Z0-9_.-]+)"\s*:', text))


def test_progress_container_and_aria_attributes():
    html = _read("web/index.html")
    assert 'id="job-progress"' in html
    assert 'id="scan-summary"' in html
    assert 'role="progressbar"' in html
    assert 'aria-valuemin="0"' in html
    assert 'aria-valuemax="100"' in html
    assert "/css/progress.css" in html


def test_progress_bar_component_contract():
    source = _read("web/js/views/progress-bar.js")
    for token in ('aria-valuenow', 'aria-valuetext', 'aria-busy', 'role="progressbar"'):
        assert token in source or token in _read("web/index.html")
    assert 'clear.type = "button"' in source
    assert "textContent" in source
    assert "innerHTML" not in source
    assert "ProgressModel" in source


def test_progress_css_motion_and_focus():
    css = _read("web/css/progress.css")
    assert "prefers-reduced-motion" in css
    assert "outline: none" not in css
    assert ":focus-visible" in css
    assert "keyframes" in css


def test_phase_keys_are_bilingual_and_complete():
    zh = _i18n_keys(_read("web/js/i18n/zh.js"))
    en = _i18n_keys(_read("web/js/i18n/en.js"))
    assert zh == en
    for phase in ("walk", "parse", "write", "build", "ai", "classify", "export", "unknown"):
        key = "phase.%s" % phase
        assert key in zh
        assert key in en
    for key in (
        "progress.summary",
        "progress.walk",
        "progress.indeterminate",
        "progress.cancelling",
        "progress.succeeded",
        "progress.cancelled",
        "progress.failed",
        "summary.found",
        "summary.limit",
        "summary.timeout",
        "summary.clear",
    ):
        assert key in zh
        assert key in en


def test_progress_files_have_no_external_links_or_packages():
    for rel_path in (
        "web/js/util/progress-model.js",
        "web/js/util/phases.js",
        "web/js/views/progress-bar.js",
        "web/css/progress.css",
    ):
        text = _read(rel_path)
        assert "http://" not in text
        assert "https://" not in text
        assert "require(" not in text
        assert "from \"node:" not in text
        assert "from 'node:" not in text