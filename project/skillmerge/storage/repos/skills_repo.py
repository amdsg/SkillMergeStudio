from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..db import Database
from ..models import Skill, dumps


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class SkillsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_many(self, skills: Iterable[Skill], locations: Optional[Iterable[Any]] = None) -> int:
        items = list(skills)
        locs = [loc.to_row() if hasattr(loc, "to_row") else dict(loc) for loc in (locations or [])]
        if not items:
            return 0
        with self.db.write_tx() as conn:
            for skill in items:
                self._upsert_skill(conn, skill)
            primary_ids = sorted({str(row["skill_id"]) for row in locs if int(row.get("is_primary", 0)) == 1})
            if primary_ids:
                marks = ",".join("?" for _ in primary_ids)
                conn.execute(f"UPDATE skill_locations SET is_primary=0 WHERE skill_id IN ({marks})", primary_ids)
            for row in locs:
                self._upsert_location(conn, row)
        return len(items)

    @staticmethod
    def _upsert_skill(conn, skill: Skill) -> None:
        conn.execute(
            """
            INSERT INTO skills (
                id, path, real_path, name, description, body_preview, search_blob,
                frontmatter_json, headings_json, resources_json, dependencies_json,
                warnings_json, category, category_source, confidence, platform_origin,
                size_bytes, lines, chars, mtime, content_hash, quality_score, quality_json,
                parse_error, missing, first_seen, last_seen
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(real_path) DO UPDATE SET
                path=excluded.path, name=excluded.name, description=excluded.description,
                body_preview=excluded.body_preview, search_blob=excluded.search_blob,
                frontmatter_json=excluded.frontmatter_json, headings_json=excluded.headings_json,
                resources_json=excluded.resources_json, dependencies_json=excluded.dependencies_json,
                warnings_json=excluded.warnings_json, confidence=excluded.confidence,
                platform_origin=excluded.platform_origin, size_bytes=excluded.size_bytes,
                lines=excluded.lines, chars=excluded.chars, mtime=excluded.mtime,
                content_hash=excluded.content_hash, quality_score=excluded.quality_score,
                quality_json=excluded.quality_json, parse_error=excluded.parse_error,
                missing=excluded.missing, last_seen=excluded.last_seen
            """,
            (
                skill.id, skill.path, skill.real_path, skill.name, skill.description,
                skill.body_preview, skill.search_blob, skill.frontmatter_json,
                skill.headings_json, skill.resources_json, skill.dependencies_json,
                skill.warnings_json, skill.category, skill.category_source, skill.confidence,
                skill.platform_origin, skill.size_bytes, skill.lines, skill.chars, skill.mtime,
                skill.content_hash, skill.quality_score, skill.quality_json, skill.parse_error,
                skill.missing, skill.first_seen, skill.last_seen,
            ),
        )

    @staticmethod
    def _upsert_location(conn, row: Dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO skill_locations (skill_id, path, real_path, platform, is_primary, mtime, size_bytes, last_seen)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(real_path) DO UPDATE SET
                skill_id=excluded.skill_id, path=excluded.path, platform=excluded.platform,
                is_primary=excluded.is_primary, mtime=excluded.mtime,
                size_bytes=excluded.size_bytes, last_seen=excluded.last_seen
            """,
            (
                row["skill_id"], row["path"], row["real_path"], row.get("platform", "unknown"),
                int(row.get("is_primary", 0)), float(row.get("mtime", 0.0)),
                int(row.get("size_bytes", 0)), row.get("last_seen", ""),
            ),
        )

    def replace_primary(self, skill_id: str, location: Any) -> None:
        row = location.to_row() if hasattr(location, "to_row") else dict(location)
        with self.db.write_tx() as conn:
            conn.execute("UPDATE skill_locations SET is_primary=0 WHERE skill_id=?", (skill_id,))
            conn.execute(
                """
                INSERT INTO skill_locations (skill_id, path, real_path, platform, is_primary, mtime, size_bytes, last_seen)
                VALUES (?,?,?,?,1,?,?,?)
                ON CONFLICT(real_path) DO UPDATE SET skill_id=excluded.skill_id, path=excluded.path,
                    platform=excluded.platform, is_primary=1, mtime=excluded.mtime,
                    size_bytes=excluded.size_bytes, last_seen=excluded.last_seen
                """,
                (
                    skill_id, row["path"], row["real_path"], row.get("platform", "unknown"),
                    float(row.get("mtime", 0.0)), int(row.get("size_bytes", 0)), row.get("last_seen", ""),
                ),
            )

    def get(self, skill_id: str) -> Optional[Skill]:
        row = self.db.query_one("SELECT * FROM skills WHERE id=?", (skill_id,))
        return Skill.from_row(row) if row else None

    def get_by_real_path(self, real_path: str) -> Optional[Skill]:
        row = self.db.query_one("SELECT * FROM skills WHERE real_path=?", (real_path,))
        return Skill.from_row(row) if row else None

    def get_by_hash(self, content_hash: str) -> List[Skill]:
        rows = self.db.query_all("SELECT * FROM skills WHERE content_hash=? ORDER BY real_path", (content_hash,))
        return [Skill.from_row(row) for row in rows]

    def locations(self, skill_id: str) -> List[Dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT * FROM skill_locations WHERE skill_id=? ORDER BY is_primary DESC, real_path", (skill_id,)
        )
        return [dict(row) for row in rows]

    def all_paths(self) -> List[Tuple[str, str, int]]:
        rows = self.db.query_all("SELECT id, path, missing FROM skills ORDER BY real_path")
        return [(str(row["id"]), str(row["path"]), int(row["missing"])) for row in rows]

    def mark_missing(self, skill_ids: Iterable[str]) -> int:
        ids = [str(item) for item in skill_ids]
        if not ids:
            return 0

        def run(conn, chunk):
            placeholders = ",".join("?" for _ in chunk)
            cursor = conn.execute(f"UPDATE skills SET missing=1 WHERE id IN ({placeholders})", chunk)
            return cursor.rowcount

        changed = 0
        for start in range(0, len(ids), 500):
            with self.db.write_tx() as conn:
                changed += run(conn, ids[start:start + 500])
        return changed

    def update_touch(self, pairs: Iterable[Tuple[str, str]]) -> None:
        items = list(pairs)
        if not items:
            return
        with self.db.write_tx() as conn:
            conn.executemany("UPDATE skills SET last_seen=? WHERE id=?", items)

    def update_category(self, skill_id: str, category: str, source: str, confidence: float) -> bool:
        with self.db.write_tx() as conn:
            cursor = conn.execute(
                "UPDATE skills SET category=?, category_source=?, confidence=? WHERE id=?",
                (category, source, float(confidence), skill_id),
            )
            return cursor.rowcount > 0

    def update_quality(self, skill_id: str, score: int, quality_json: str, warnings_json: str) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE skills SET quality_score=?, quality_json=?, warnings_json=? WHERE id=?",
                (int(score), quality_json, warnings_json, skill_id),
            )

    def update_missing_flag(self, skill_id: str, missing: int) -> None:
        with self.db.write_tx() as conn:
            conn.execute("UPDATE skills SET missing=? WHERE id=?", (int(missing), skill_id))

    def _where(self, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
        clauses: List[str] = ["1=1"]
        params: List[Any] = []
        if filters.get("category"):
            clauses.append("s.category=?")
            params.append(str(filters["category"]))
        if filters.get("platform"):
            clauses.append(
                "(s.platform_origin=? OR EXISTS (SELECT 1 FROM skill_locations l WHERE l.skill_id=s.id AND l.platform=?))"
            )
            params.extend([str(filters["platform"]), str(filters["platform"])])
        if filters.get("q"):
            clauses.append(
                "(s.name LIKE ? ESCAPE '\\' OR s.description LIKE ? ESCAPE '\\' OR s.search_blob LIKE ? ESCAPE '\\')"
            )
            needle = _like(str(filters["q"]))
            params.extend([needle, needle, needle])
        if filters.get("quality_min") is not None:
            clauses.append("s.quality_score>=?")
            params.append(int(filters["quality_min"]))
        if filters.get("quality_max") is not None:
            clauses.append("s.quality_score<=?")
            params.append(int(filters["quality_max"]))
        if filters.get("size_min") is not None:
            clauses.append("s.size_bytes>=?")
            params.append(int(filters["size_min"]))
        if filters.get("size_max") is not None:
            clauses.append("s.size_bytes<=?")
            params.append(int(filters["size_max"]))
        if filters.get("mtime_from"):
            clauses.append("s.mtime>=?")
            params.append(float(filters["mtime_from"]))
        if filters.get("mtime_after"):
            clauses.append("s.mtime>=?")
            params.append(float(filters["mtime_after"]))
        if filters.get("has_resources"):
            clauses.append("s.resources_json NOT IN ('[]','')")
        if filters.get("parse_error"):
            clauses.append("s.parse_error IS NOT NULL")
        if not filters.get("include_missing"):
            clauses.append("s.missing=0")
        if filters.get("duplicate") == "only":
            clauses.append(
                "(SELECT COUNT(*) FROM skill_locations l WHERE l.skill_id=s.id)>1"
                " OR s.content_hash IN (SELECT content_hash FROM skills GROUP BY content_hash HAVING COUNT(*)>1)"
            )
        elif filters.get("duplicate") == "exclude":
            clauses.append(
                "(SELECT COUNT(*) FROM skill_locations l WHERE l.skill_id=s.id)<=1"
                " AND s.content_hash NOT IN (SELECT content_hash FROM skills GROUP BY content_hash HAVING COUNT(*)>1)"
            )
        return " AND ".join(clauses), params

    def list(self, filters: Dict[str, Any], limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        where, params = self._where(filters)
        total = int(self.db.scalar(f"SELECT COUNT(*) FROM skills s WHERE {where}", params) or 0)
        sort = str(filters.get("sort") or "name")
        order = {
            "name": "s.name COLLATE NOCASE, s.id",
            "quality": "s.quality_score DESC, s.id",
            "size": "s.size_bytes DESC, s.id",
            "mtime": "s.mtime DESC, s.id",
        }.get(sort, "s.name COLLATE NOCASE, s.id")
        sql = (
            "SELECT s.*, (SELECT COUNT(*) FROM skill_locations l WHERE l.skill_id=s.id) AS locations_count "
            f"FROM skills s WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?"
        )
        rows = self.db.query_all(sql, params + [int(limit), int(offset)])
        items = []
        for row in rows:
            data = dict(row)
            count = int(data.pop("locations_count", 0) or 0)
            data["locations_count"] = max(count, 1)
            items.append(data)
        return items, total

    def categories_with_counts(self) -> List[Dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT category AS name, COUNT(*) AS count FROM skills WHERE missing=0 GROUP BY category ORDER BY category"
        )
        return [{"name": str(row["name"]), "count": int(row["count"])} for row in rows]

    def duplicate_groups(self) -> List[Dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT content_hash AS hash, COUNT(*) AS count, GROUP_CONCAT(id) AS ids
            FROM skills GROUP BY content_hash HAVING COUNT(*)>1 ORDER BY count DESC, hash
            """
        )
        return [{"hash": row["hash"], "count": int(row["count"]), "ids": str(row["ids"]).split(",")} for row in rows]

    def counts(self) -> Dict[str, int]:
        row = self.db.query_one(
            "SELECT COUNT(*) AS total, SUM(missing) AS missing, SUM(CASE WHEN quality_score<60 THEN 1 ELSE 0 END) AS low FROM skills"
        )
        if not row:
            return {"total": 0, "missing": 0, "low": 0}
        return {
            "total": int(row["total"] or 0),
            "missing": int(row["missing"] or 0),
            "low": int(row["low"] or 0),
        }


def normalize_real_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))