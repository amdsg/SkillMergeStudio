from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..db import Database
from ..models import Scan, ScanStats, dumps, loads


class ScansRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, scan: Scan) -> int:
        with self.db.write_tx() as conn:
            cursor = conn.execute(
                "INSERT INTO scans (job_id, mode, roots_json, started_at, finished_at, stats_json, coverage_json) VALUES (?,?,?,?,?,?,?)",
                (
                    scan.job_id, scan.mode, scan.roots_json, scan.started_at, scan.finished_at,
                    scan.stats_json, scan.coverage_json,
                ),
            )
            return int(cursor.lastrowid)

    def finish(self, scan_id: int, finished_at: str, stats: ScanStats, coverage: List[str]) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE scans SET finished_at=?, stats_json=?, coverage_json=? WHERE id=?",
                (finished_at, dumps(stats.to_dict()), dumps(coverage), int(scan_id)),
            )

    def get(self, scan_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.query_one("SELECT * FROM scans WHERE id=?", (int(scan_id),))
        if not row:
            return None
        data = dict(row)
        data["stats"] = loads(data.pop("stats_json", "{}"), {})
        data["coverage"] = loads(data.pop("coverage_json", "[]"), [])
        return data

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.query_all("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (int(limit),))
        items = []
        for row in rows:
            data = dict(row)
            data["stats"] = loads(data.pop("stats_json", "{}"), {})
            data["coverage"] = loads(data.pop("coverage_json", "[]"), [])
            items.append(data)
        return items