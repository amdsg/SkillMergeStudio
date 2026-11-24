from __future__ import annotations

import os
import time

from skillmerge.services.scanner.scanner_service import ScanOptions, ScannerService
from skillmerge.config.loader import load_config
from skillmerge.storage.db import Database


def _make_skills(root, count):
    for index in range(count):
        folder = os.path.join(root, f"skill-{index:04d}")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "SKILL.md"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(f"---\nname: skill-{index:04d}\ndescription: 性能测试技能 {index}\n---\n\n# Skill {index}\n\n正文内容。\n")


def test_incremental_rescan_1000_under_two_seconds(tmp_path):
    root = str(tmp_path / "skills")
    os.makedirs(root, exist_ok=True)
    _make_skills(root, 1000)
    data_dir = str(tmp_path / "data")
    config, _ = load_config(data_dir)
    db = Database(str(tmp_path / "index.db"))
    db.initialize()
    service = ScannerService(db, config)
    first = service.scan(options=ScanOptions(roots=[root], depth=10))
    assert first["stats"]["found"] == 1000
    started = time.monotonic()
    second = service.scan(options=ScanOptions(roots=[root], depth=10))
    elapsed = time.monotonic() - started
    db.close_all()
    assert second["stats"]["body_reads"] == 0
    assert second["stats"]["new"] == 0
    assert elapsed < 2.0, f"复扫耗时 {elapsed:.3f}s"