from __future__ import annotations

import os

from skillmerge.config.loader import load_config
from skillmerge.services.scanner.scanner_service import ScanOptions, ScannerService
from skillmerge.storage.db import Database
from skillmerge.storage.repos.skills_repo import SkillsRepo

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
SKILLS = os.path.join(FIXTURES, "skills")


def _service(tmp_path):
    data_dir = str(tmp_path / "data")
    config, _ = load_config(data_dir)
    db = Database(str(tmp_path / "index.db"))
    db.initialize()
    return ScannerService(db, config), db


def test_scan_finds_nested_and_prunes_node_modules(tmp_path):
    service, db = _service(tmp_path)
    result = service.scan(options=ScanOptions(roots=[SKILLS], depth=10))
    paths = [item["path"].replace("\\", "/") for item in result["items"]]
    assert any("/a/b/c/d/" in path for path in paths)
    assert any("basic" in path for path in paths)
    assert not any("node_modules" in path for path in paths)
    assert result["stats"]["new"] >= 4
    db.close_all()


def test_duplicate_content_collapses_locations(tmp_path):
    service, db = _service(tmp_path)
    result = service.scan(options=ScanOptions(roots=[SKILLS], depth=10))
    copies = [item for item in result["items"] if item["name"] == "copy-skill"]
    assert len(copies) == 1
    assert copies[0]["copies"] == 3
    repo = SkillsRepo(db)
    locations = repo.locations(copies[0]["id"])
    assert len(locations) == 3
    assert sum(int(loc["is_primary"]) for loc in locations) == 1
    db.close_all()


def test_incremental_rescan_reads_no_body(tmp_path):
    service, db = _service(tmp_path)
    first = service.scan(options=ScanOptions(roots=[SKILLS], depth=10))
    assert first["stats"]["body_reads"] > 0
    second = service.scan(options=ScanOptions(roots=[SKILLS], depth=10))
    assert second["stats"]["body_reads"] == 0
    assert second["stats"]["new"] == 0
    db.close_all()


def test_broken_record_is_kept(tmp_path):
    service, db = _service(tmp_path)
    service.scan(options=ScanOptions(roots=[SKILLS], depth=10))
    rows = db.query_all("SELECT name, parse_error, quality_score, path FROM skills")
    broken = [row for row in rows if "broken" in str(row["path"]).replace("\\", "/")]
    assert broken
    assert broken[0]["parse_error"] or broken[0]["quality_score"] < 100
    db.close_all()