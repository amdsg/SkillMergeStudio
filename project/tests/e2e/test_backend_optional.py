from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _driver import backend_capabilities  # noqa: E402

pytestmark = pytest.mark.e2e


def test_backend_is_optional(browser_backend):
    capabilities = backend_capabilities(browser_backend)
    assert capabilities["auto_dom"] is (browser_backend == "playwright")