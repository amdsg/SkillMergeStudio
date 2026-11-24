import json
import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.api import install_apply  # noqa: E402
from agent.core import atomic_write, rollback  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402


def payload(sandbox: Path, files: list[dict], plan_hash="plan-1") -> bytes:
    return json.dumps({
        "target_path": str(sandbox),
        "plan_hash": plan_hash,
        "confirm_token": install_apply.confirm_token(plan_hash),
        "files": files,
    }).encode("utf-8")


def enable(monkeypatch, tmp_path):
    monkeypatch.setattr(install_apply, "is_enabled", lambda capability_id: True)
    monkeypatch.setattr(install_apply, "SANDBOX", tmp_path / "sandbox")
    monkeypatch.setattr(install_apply, "BACKUPS", tmp_path / "backups")
    (tmp_path / "sandbox").mkdir(parents=True, exist_ok=True)


def test_capability_off_returns_403(monkeypatch, tmp_path):
    monkeypatch.setattr(install_apply, "is_enabled", lambda capability_id: False)
    with pytest.raises(DomainError) as error:
        install_apply.apply_endpoint({}, payload(tmp_path / "sandbox", [{"path": "a.md", "content": "x"}]), "")
    assert error.value.code == "E_CAPABILITY_DISABLED"


def test_outside_sandbox_is_denied(monkeypatch, tmp_path):
    enable(monkeypatch, tmp_path)
    with pytest.raises(DomainError) as error:
        install_apply.apply_endpoint({}, payload(tmp_path / "elsewhere", [{"path": "a.md", "content": "x"}]), "")
    assert error.value.code == "E_PATH_DENIED"


def test_bad_confirm_token_is_rejected(monkeypatch, tmp_path):
    enable(monkeypatch, tmp_path)
    body = json.loads(payload(tmp_path / "sandbox", [{"path": "a.md", "content": "x"}]))
    body["confirm_token"] = "wrong"
    with pytest.raises(DomainError) as error:
        install_apply.apply_endpoint({}, json.dumps(body).encode("utf-8"), "")
    assert error.value.code == "E_CONFIRM_REQUIRED"


def test_success_writes_and_backs_up(monkeypatch, tmp_path):
    enable(monkeypatch, tmp_path)
    sandbox = tmp_path / "sandbox"
    (sandbox / "SKILL.md").write_text("old", encoding="utf-8")
    result = install_apply.apply_endpoint({}, payload(sandbox, [{"path": "SKILL.md", "content": "new"}]), "")
    assert result["state"] == "succeeded"
    assert (sandbox / "SKILL.md").read_text(encoding="utf-8") == "new"
    assert (tmp_path / "backups").is_dir()


def test_failure_rolls_back_created_and_restored(monkeypatch, tmp_path):
    enable(monkeypatch, tmp_path)
    sandbox = tmp_path / "sandbox"
    (sandbox / "SKILL.md").write_text("old", encoding="utf-8")
    calls = {"count": 0}
    real_write = atomic_write.write_text

    def failing_write(path, text):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("injected failure")
        return real_write(path, text)

    monkeypatch.setattr(atomic_write, "write_text", failing_write)
    with pytest.raises(DomainError) as error:
        install_apply.apply_endpoint({}, payload(sandbox, [
            {"path": "SKILL.md", "content": "new"},
            {"path": "second.md", "content": "second"},
        ]), "")
    assert error.value.code == "E_WRITE_FAILED"
    assert (sandbox / "SKILL.md").read_text(encoding="utf-8") == "old"
    assert not (sandbox / "second.md").exists()


def test_rollback_failure_reports_rollback_failed(monkeypatch, tmp_path):
    enable(monkeypatch, tmp_path)
    monkeypatch.setattr(rollback, "rollback", lambda *args, **kwargs: {"ok": False, "errors": [{"path": "a.md"}], "restored": [], "removed": []})
    original = atomic_write.write_text
    monkeypatch.setattr(atomic_write, "write_text", lambda path, text: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(DomainError) as error:
        install_apply.apply_endpoint({}, payload(tmp_path / "sandbox", [{"path": "a.md", "content": "x"}]), "")
    assert error.value.code == "E_ROLLBACK_FAILED"
    monkeypatch.setattr(atomic_write, "write_text", original)