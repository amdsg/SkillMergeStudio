from __future__ import annotations

from skillmerge.services.merger import similarity


def test_exact_match_returns_one():
    result = similarity.similarity("同一段文本", "同一段文本")
    assert result.value == 1.0
    assert result.method == "exact"


def test_short_text_never_matches():
    result = similarity.similarity("短", "完全不同")
    assert result.value == 0.0
    assert result.method == "exact-short"


def test_fast_reject_on_disjoint_text():
    left = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    right = "一二三四五六七八九十百千万亿兆京垓秭穰沟涧正载"
    result = similarity.similarity(left, right)
    assert result.value == 0.0
    assert result.method == "fast-reject"


def test_sequence_path_for_medium_text():
    left = "读取数据并生成统计报告和图表，包含步骤一与步骤二以及注意事项和示例。"
    right = "读取数据并生成统计报告和图表，包含步骤一与步骤二以及注意事项。"
    result = similarity.similarity(left, right)
    assert result.method == "sequence"
    assert isinstance(result.value, float)
    assert 0.0 < result.value < 1.0


def test_windows_small_and_large():
    assert similarity._windows("a" * 100) == ["a" * 100]
    windows = similarity._windows("a" * 2000)
    assert len(windows) == 5
    assert all(len(window) <= similarity.WINDOW_SIZE for window in windows)


def test_windowed_path_marks_truncated(monkeypatch):
    monkeypatch.setattr(similarity, "FULL_LIMIT", 10)
    left = "abcd" * 10
    right = "abce" * 10
    result = similarity.similarity(left, right, budget_ms=5000)
    assert result.method == "windowed"
    assert result.truncated is True
    assert 0.0 <= result.value <= 1.0


def test_timeout_returns_none(monkeypatch):
    monkeypatch.setattr(similarity, "FULL_LIMIT", 10)
    counter = {"value": 0}

    def fake_clock():
        counter["value"] += 1
        return float(counter["value"])

    monkeypatch.setattr(similarity.time, "monotonic", fake_clock)
    left = "abcd" * 10
    right = "abce" * 10
    result = similarity.similarity(left, right, budget_ms=1)
    assert result.value is None
    assert result.method == "timeout"
    assert result.truncated is True