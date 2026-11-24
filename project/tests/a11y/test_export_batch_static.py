from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path):
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _keys(text):
    return set(re.findall(r'"([a-zA-Z0-9_.-]+)"\s*:', text))


def test_export_containers_and_buttons():
    html = _read("web/index.html")
    for token in (
        'id="export-platforms"',
        'id="export-preview"',
        'id="export-results"',
        'id="export-preview-button"',
        'id="history-platform"',
        "/css/export-batch.css",
        'aria-live="polite"',
    ):
        assert token in html
    for tag in re.findall(r"<button[^>]*>", html):
        assert "type=" in tag, tag


def test_export_platforms_contract():
    source = _read("web/js/views/export-platforms.js")
    for token in (
        "format.install_scopes",
        "MAX_PLATFORMS",
        "export.installDisabled",
        "export.tooMany",
        'type="checkbox"',
        "installable",
        "formatBadgeHtml",
    ):
        assert token in source
    format_source = _read("web/js/views/platform-format.js")
    assert "format.package_type" in format_source
    assert "format.rule_status" in format_source
    assert "format.verified" in format_source
    assert "format.candidate" in format_source
    assert "checkbox" in source
    assert "28" in source


def test_export_results_contract():
    source = _read("web/js/views/export-results.js")
    for token in (
        "result.batch",
        "export.item.succeeded",
        "export.item.failed",
        "export.item.cancelled",
        "export.summary",
        "error.fix",
        "formatBadges",
    ):
        assert token in source
    html = _read("web/index.html")
    assert 'id="export-results"' in html
    assert 'aria-live="polite"' in html


def test_export_preview_contract():
    source = _read("web/js/views/export-preview.js")
    for token in ("planned", "validation", "requires_confirm", "export.previewTitle", "formatBadges"):
        assert token in source


def test_export_batch_css_a11y():
    css = _read("web/css/export-batch.css")
    assert "outline: none" not in css
    assert ":focus-visible" in css or ":focus-within" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (max-width: 720px)" in css


def test_export_i18n_keys_bilingual():
    zh = _keys(_read("web/js/i18n/zh.js"))
    en = _keys(_read("web/js/i18n/en.js"))
    assert zh == en
    for key in (
        "format.dir",
        "format.zip",
        "format.prompt",
        "format.wrapped",
        "format.installable",
        "format.notInstallable",
        "format.verified",
        "format.candidate",
        "format.unknown",
        "format.skillMd",
        "export.platforms",
        "export.selected",
        "export.tooMany",
        "export.installDisabled",
        "export.noPlatform",
        "export.candidateBatch",
        "export.preview",
        "export.previewTitle",
        "export.previewSummary",
        "export.results",
        "export.summary",
        "export.item.succeeded",
        "export.item.failed",
        "export.item.cancelled",
        "export.batchDone",
        "export.format",
        "export.paths",
        "export.error",
        "history.filterPlatform",
        "history.allPlatforms",
    ):
        assert key in zh, key
        assert key in en, key


def test_export_views_have_no_external_links_or_packages():
    for rel_path in (
        "web/js/views/platform-format.js",
        "web/js/views/export-platforms.js",
        "web/js/views/export-preview.js",
        "web/js/views/export-results.js",
    ):
        text = _read(rel_path)
        assert "http://" not in text
        assert "https://" not in text
        assert "require(" not in text