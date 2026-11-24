from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_driver():
    path = ROOT / "tests" / "e2e" / "_driver.py"
    spec = importlib.util.spec_from_file_location("e2e_driver", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_g01_detect_backend_does_not_raise():
    driver = _load_driver()
    assert driver.detect_backend() in (None, "playwright", "selenium")


def test_g02_default_addopts_excludes_perf_and_e2e():
    text = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert 'addopts = -m "not perf and not e2e"' in text
    assert "e2e:" in text


def test_g03_runtime_import_graph_unchanged():
    before = set(sys.modules)
    _load_driver()
    loaded = {name for name in set(sys.modules) - before if name.split(".")[0] in {"playwright", "selenium", "pyppeteer"}}
    assert loaded == set()


def test_g04_dev_requirements_do_not_preinstall_browser():
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").lower()
    assert "playwright" not in text
    assert "selenium" not in text