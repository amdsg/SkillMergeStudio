from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _driver import detect_backend  # noqa: E402


@pytest.fixture(scope="session")
def browser_backend():
    backend = detect_backend()
    if backend is None:
        pytest.skip("Q-32 未批准：未安装 Playwright/Selenium，浏览器证据只能为 manual")
    return backend