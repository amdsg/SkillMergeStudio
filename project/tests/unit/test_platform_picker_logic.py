from __future__ import annotations

import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROW_HEIGHT = 44
BUFFER = 4


def window_slice(total, scroll_top, height, row_height=ROW_HEIGHT, buffer=BUFFER):
    start = min(total, max(0, math.floor(scroll_top / row_height) - buffer))
    visible = math.ceil(height / row_height) + buffer * 2
    end = min(total, start + visible)
    return {"start": start, "end": end, "total_height": total * row_height, "dom_count": max(0, end - start)}


def test_window_limits_dom_for_28_and_200():
    for total in (28, 200):
        result = window_slice(total, 0, 280)
        assert result["dom_count"] <= math.ceil(280 / ROW_HEIGHT) + 2 * BUFFER
        assert result["total_height"] == total * ROW_HEIGHT


def test_window_scroll_clamps():
    result = window_slice(28, 10_000, 280)
    assert result["end"] <= 28
    assert result["start"] <= 28


def test_picker_uses_same_constants():
    path = os.path.join(ROOT, "web", "js", "util", "platform-window.js")
    text = open(path, "r", encoding="utf-8").read()
    assert "ROW_HEIGHT = 44" in text
    assert "BUFFER = 4" in text
    assert "windowSlice" in text