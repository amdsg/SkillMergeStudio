from __future__ import annotations

import argparse
import json
import os

from skillmerge.cli.commands import run_classify, run_export, run_merge, run_validate
from skillmerge.config import paths
from skillmerge.config.loader import load_config
from skillmerge.services.scanner.scanner_service import ScanOptions, ScannerService
from skillmerge.storage.db import Database
from tests.helpers import write_skill


def _args(**kwargs):
    base = {"data_dir": "", "json": True}
    base.update(kwargs)
    return argparse.Namespace(**base)


def _prepare(tmp_path, capsys):
    root = tmp_path / "skills"
    write_skill(root, "alpha", "alpha", "生成统计报告和数据图表", "# Alpha\n\n## 流程\n\n步骤一\n\n```bash\nls\n```")
    write_skill(root, "beta", "beta", "整理文档与图表", "# Beta\n\n## 流程\n\n步骤二\n\n```bash\ndir\n```")
    data_dir = str(tmp_path / "data")
    config, _warnings = load_config(data_dir)
    db = Database(paths.db_path(data_dir))
    db.initialize()
    ScannerService(db, config).scan(options=ScanOptions(roots=[str(root)], depth=5))
    ids = [row["id"] for row in db.query_all("SELECT id FROM skills ORDER BY name")]
    db.close_all()
    capsys.readouterr()
    return data_dir, ids


def test_cli_merge_validate_export_classify(tmp_path, capsys):
    data_dir, ids = _prepare(tmp_path, capsys)
    assert len(ids) == 2

    code = run_merge(
        _args(
            sources=",".join(ids),
            name="demo-merge",
            platform="generic",
            strategy="keep-all",
            out="",
            use_ai=False,
            confirm_ai=False,
            data_dir=data_dir,
        )
    )
    assert code == 0
    merged = json.loads(capsys.readouterr().out)
    assert merged["ok"] is True
    artifact = merged["data"]
    assert os.path.isdir(artifact["dir_path"])

    code = run_validate(_args(artifact=artifact["dir_path"], platform="generic", name_en="", data_dir=data_dir))
    assert code in (0, 1)
    validated = json.loads(capsys.readouterr().out)
    assert validated["ok"] is True
    assert validated["data"]["name"]
    assert validated["data"]["error_count"] == 0

    code = run_export(
        _args(
            artifact=artifact["artifact_id"],
            platform="generic",
            mode="zip",
            install_scope="global",
            length_mode="full",
            profile="generic",
            name_en="",
            confirm_candidate=False,
            data_dir=data_dir,
        )
    )
    assert code == 0
    exported = json.loads(capsys.readouterr().out)["data"]
    assert exported["zip_path"] and os.path.isfile(exported["zip_path"])

    code = run_classify(_args(skill_ids="", use_ai=False, confirm_ai=False, data_dir=data_dir))
    assert code == 0
    classified = json.loads(capsys.readouterr().out)
    assert classified["ok"] is True


def test_cli_missing_skill_returns_two(tmp_path, capsys):
    data_dir = str(tmp_path / "data")
    code = run_merge(
        _args(
            sources="missing-id",
            name="demo",
            platform="generic",
            strategy="keep-all",
            out="",
            use_ai=False,
            confirm_ai=False,
            data_dir=data_dir,
        )
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "NOT_FOUND"


def test_cli_validate_rejects_non_artifact(tmp_path, capsys):
    code = run_validate(_args(artifact=str(tmp_path), platform="generic", name_en="", data_dir=str(tmp_path / "data")))
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "INVALID_ARGUMENT"