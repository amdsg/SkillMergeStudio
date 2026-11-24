from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def probe():
    spec = importlib.util.spec_from_file_location("ai_quality_probe", ROOT / "tools" / "ai_quality_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a01_home_is_masked(probe):
    text, applied, count = probe.sanitize(r"C:\Users\bob\skills\a.md")
    assert "<home>" in text
    assert "bob" not in text


def test_a02_secret_is_masked(probe):
    text, _applied, _count = probe.sanitize("token=sk-abcdefgh1234")
    assert "sk-abcdefgh1234" not in text
    assert "<secret>" in text


def test_a03_second_scan_aborts(probe, monkeypatch):
    monkeypatch.setattr(probe, "RULES", ())
    with pytest.raises(ValueError) as exc:
        probe.sanitize("sk-abcdefgh1234")
    assert "M6-SANITIZE-LEAK" in str(exc.value)


def test_a04_budget_stops(probe):
    budget = probe.Budget(100)
    assert budget.add(40)
    assert budget.add(40)
    assert not budget.add(40)
    assert budget.stopped_reason == "budget_exhausted"


def test_a05_gate_blocked_without_endpoint(probe, monkeypatch):
    class Config:
        ai = type("AI", (), {"enabled": False, "base_url": "", "model": ""})()

    state, missing, key = probe.gate(Config(), "SKILLMERGE_API_KEY", "", 0)
    assert state == "blocked"
    assert "missing_endpoint" in missing
    assert "missing_budget_auth" in missing


def test_a06_dry_run_refuses_real_report_name(probe, tmp_path, monkeypatch):
    monkeypatch.setattr(probe.paths, "data_dir", lambda: str(tmp_path / "data"))
    code = probe.main(["--dry-run", "--out", str(tmp_path / "ai-quality-real.json")])
    assert code == 1
    assert not (tmp_path / "ai-quality-real.json").exists()


def test_a07_rerun_without_tolerance_is_cannot_judge(probe):
    result = probe.rerun_compare({"agreement_rate": 0.9}, {"agreement_rate": 0.8}, None)
    assert result["verdict"] == "cannot-judge"
    assert result["tolerance"] is None


def test_a08_existing_report_requires_force(probe, tmp_path):
    target = tmp_path / "ai-quality-simulated-1.json"
    target.write_text("{}", encoding="utf-8")
    assert probe.write_report(target, {"result": "blocked"}, False) == 1
    assert probe.write_report(target, {"result": "blocked"}, True) == 0


def test_a09_report_never_contains_key(probe, monkeypatch):
    class Config:
        ai = type("AI", (), {"enabled": True, "base_url": "https://api.example.com/v1", "model": "m"})()

    class Args:
        budget_tokens = 1000
        samples = 30
        merge_sets = 3

    payload = probe.base_report(Config(), "sk-secret-abcdefgh", Args())
    text = json.dumps(payload)
    assert "sk-secret-abcdefgh" not in text
    assert payload["key_fingerprint"]


def test_a10_authorized_never_fakes_pass(probe, tmp_path, monkeypatch):
    class Config:
        ai = type("AI", (), {"enabled": True, "base_url": "https://api.example.com/v1", "model": "m"})()

    monkeypatch.setattr(probe, "load_config", lambda _dir: (Config(), []))
    monkeypatch.setenv("SKILLMERGE_API_KEY", "sk-secret-abcdefgh")
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "a.md").write_text("# a", encoding="utf-8")
    code = probe.main(
        [
            "--config",
            str(tmp_path),
            "--sample-dir",
            str(sample_dir),
            "--budget-tokens",
            "1000",
            "--dry-run",
        ]
    )
    assert code == 0