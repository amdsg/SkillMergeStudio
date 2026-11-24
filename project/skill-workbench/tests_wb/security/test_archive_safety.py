import sys
import zipfile
from pathlib import Path

import pytest

WB_ROOT = Path(__file__).resolve().parents[2]
if str(WB_ROOT) not in sys.path:
    sys.path.insert(0, str(WB_ROOT))

from agent.core import archive  # noqa: E402
from agent.core.archive import copy_tree, extract_zip  # noqa: E402
from agent.core.source_ref import build, validate  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402


def test_zip_slip_is_rejected(tmp_path):
    bundle = tmp_path / "bad.zip"
    with zipfile.ZipFile(bundle, "w") as handle:
        handle.writestr("../escape.txt", "escape")
    with pytest.raises(DomainError) as error:
        extract_zip(bundle, tmp_path / "dest")
    assert error.value.code == "E_LINK_ESCAPE"
    assert not (tmp_path / "escape.txt").exists()


def test_scripts_and_binaries_are_ignored(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (source / "run.sh").write_text("echo no\n", encoding="utf-8")
    (source / "bin.exe").write_bytes(b"MZ")
    files, ignored = copy_tree(source, tmp_path / "dest")
    assert files == ["SKILL.md"]
    reasons = {item["name"]: item["reason"] for item in ignored}
    assert reasons == {"run.sh": "script", "bin.exe": "binary"}


def test_single_file_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(archive, "MAX_FILE_BYTES", 4)
    source = tmp_path / "source"
    source.mkdir()
    (source / "big.md").write_text("0123456789", encoding="utf-8")
    with pytest.raises(DomainError) as error:
        copy_tree(source, tmp_path / "dest")
    assert error.value.code == "E_ARCHIVE_TOO_LARGE"


def test_source_ref_missing_signal():
    ref = build("fixture/skill-alpha", commit_sha="")
    assert validate(ref) == ["commit_sha", "archive_hash"]
    ref = build("fixture/skill-alpha", commit_sha="a" * 40, archive_hash="b" * 64)
    assert validate(ref) == []