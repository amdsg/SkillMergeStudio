from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def test_platform_picker_markup_and_wiring():
    html = read("web/index.html")
    assert 'role="combobox"' in html
    assert 'role="listbox"' in html
    assert 'id="platform-listbox"' in html
    assert 'id="platform-counts"' in html
    assert 'id="candidate-pool-modal"' in html
    app = read("web/js/app.js")
    assert "createPlatformPicker" in app
    assert "createCandidatePool" in app
    assert "confirm_candidate" in app
    picker = read("web/js/views/platform-picker.js")
    assert "aria-activedescendant" in picker
    assert "sms.platform.recent" in picker
    assert "sms.platform.groups" in picker
    assert "windowSlice" in picker
    assert 't("candidate.header")' in picker


def test_counts_strip_template_is_dynamic():
    app = read("web/js/app.js")
    panel = read("web/js/views/status-panel.js")
    zh = read("web/js/i18n/zh.js")
    assert "renderPlatformCounts" in app
    for token in ("evidence_total", "evidence_skill", "evidence_rules", "evidence_discovery"):
        assert token in panel
    for token in ("已核验", "官方", "本地契约", "发现证据", "最后核验"):
        assert token in zh


def test_no_fixed_platform_count_markup():
    html = read("web/index.html")
    for token in ("支持 27", "支持 28", "支持 100"):
        assert token not in html