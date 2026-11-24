from __future__ import annotations

import difflib
import time
from dataclasses import dataclass
from typing import Optional

from ...util.textnorm import normalize_paragraph

SHORT_TEXT = 20
FAST_REJECT = 0.30
FULL_LIMIT = 4000
WINDOW_SIZE = 500
WINDOW_STEP = 400
MAX_WINDOWS = 12
DEFAULT_BUDGET_MS = 200


@dataclass
class Similarity:
    value: Optional[float]
    method: str
    truncated: bool = False


def _jaccard(a: str, b: str) -> float:
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 1.0
    union = len(set_a | set_b)
    return len(set_a & set_b) / union if union else 0.0


def _windows(text: str):
    if len(text) <= WINDOW_SIZE:
        return [text]
    result = []
    start = 0
    while start < len(text) and len(result) < MAX_WINDOWS:
        result.append(text[start:start + WINDOW_SIZE])
        start += WINDOW_STEP
    return result


def _windowed(a: str, b: str, deadline: float) -> Optional[float]:
    windows_a = _windows(a)
    windows_b = _windows(b)
    total = 0.0
    weight_sum = 0
    for window_a in windows_a:
        best = 0.0
        for window_b in windows_b:
            if time.monotonic() > deadline:
                return None
            best = max(best, difflib.SequenceMatcher(None, window_a, window_b, autojunk=False).ratio())
        total += best * len(window_a)
        weight_sum += len(window_a)
    return total / weight_sum if weight_sum else 0.0


def similarity(a: str, b: str, budget_ms: int = DEFAULT_BUDGET_MS) -> Similarity:
    started = time.monotonic()
    deadline = started + max(1, budget_ms) / 1000.0
    left = normalize_paragraph(a)
    right = normalize_paragraph(b)
    if left == right:
        return Similarity(1.0, "exact")
    if len(left) < SHORT_TEXT or len(right) < SHORT_TEXT:
        return Similarity(0.0, "exact-short")
    if left > right:
        left, right = right, left
    if _jaccard(left, right) < FAST_REJECT:
        return Similarity(0.0, "fast-reject")
    if max(len(left), len(right)) <= FULL_LIMIT:
        value = difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()
        if time.monotonic() > deadline:
            return Similarity(None, "timeout", True)
        return Similarity(round(value, 3), "sequence")
    value = _windowed(left, right, deadline)
    if value is None:
        return Similarity(None, "timeout", True)
    return Similarity(round(value, 3), "windowed", True)