from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..db import Database
from ..models import Artifact, MergeSource, dumps


class ArtifactsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, artifact: Artifact, sources: List[MergeSource] = None) -> None:
        row = artifact.to_row()
        columns = ",".join(row.keys())
        marks = ",".join("?" for _ in row)
        with self.db.write_tx() as conn:
            conn.execute(f"INSERT INTO artifacts ({columns}) VALUES ({marks})", tuple(row.values()))
            for source in sources or []:
                conn.execute(
                    "INSERT OR REPLACE INTO merge_sources (artifact_id, skill_id, source_hash, path) VALUES (?,?,?,?)",
                    (source.artifact_id, source.skill_id, source.source_hash, source.path),
                )

    def get(self, artifact_id: str) -> Optional[Artifact]:
        row = self.db.query_one("SELECT * FROM artifacts WHERE id=?", (artifact_id,))
        return Artifact.from_row(row) if row else None

    def list(self, limit: int = 50, offset: int = 0, platform: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where = "WHERE 1=1"
        if platform:
            where += " AND platform=?"
            params.append(platform)
        rows = self.db.query_all(
            f"SELECT * FROM artifacts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [int(limit), int(offset)],
        )
        return [dict(row) for row in rows]

    def count(self, platform: str = "") -> int:
        if platform:
            return int(self.db.scalar("SELECT COUNT(*) FROM artifacts WHERE platform=?", (platform,)) or 0)
        return int(self.db.scalar("SELECT COUNT(*) FROM artifacts") or 0)

    def mark_undone(self, artifact_id: str, trash_path: str, undone_at: str) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE artifacts SET status='undone', trash_path=?, undone_at=? WHERE id=?",
                (trash_path, undone_at, artifact_id),
            )

    def mark_missing(self, artifact_id: str) -> None:
        with self.db.write_tx() as conn:
            conn.execute("UPDATE artifacts SET status='missing' WHERE id=?", (artifact_id,))

    def sources(self, artifact_id: str) -> List[Dict[str, Any]]:
        rows = self.db.query_all("SELECT * FROM merge_sources WHERE artifact_id=? ORDER BY path", (artifact_id,))
        return [dict(row) for row in rows]

    def artifacts_for_skill(self, skill_id: str) -> List[Dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT a.* FROM artifacts a JOIN merge_sources m ON m.artifact_id=a.id WHERE m.skill_id=? ORDER BY a.created_at DESC",
            (skill_id,),
        )
        return [dict(row) for row in rows]

    def set_paths(self, artifact_id: str, zip_path: Optional[str] = None, installed_path: Optional[str] = None) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE artifacts SET zip_path=COALESCE(?, zip_path), installed_path=COALESCE(?, installed_path) WHERE id=?",
                (zip_path, installed_path, artifact_id),
            )
    def update_integrity(self, artifact_id: str, sha256: str, size_bytes: int, manifest_json: str) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE artifacts SET sha256=?, size_bytes=?, manifest_json=? WHERE id=?",
                (sha256, int(size_bytes), manifest_json, artifact_id),
            )