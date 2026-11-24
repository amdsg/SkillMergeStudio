from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...config import defaults
from ...config.paths import is_within
from ...storage.models import Scan, Skill, SkillLocation, dumps
from ...storage.repos.scans_repo import ScansRepo
from ...storage.repos.skills_repo import SkillsRepo
from ...util.hashing import short_id, skill_dir_hash
from ...util.textnorm import normalize_search
from ...util.timeutil import utc_now_iso
from ..parser.frontmatter import read_document
from ..parser.markdown import parse_markdown
from ..parser.quality import directory_name_for, score_quality
from ..parser.resources import enumerate_resources, parse_dependencies
from .discover import detect_roots
from .drives import select_drives
from .stats import ScanAccumulator
from .walker import WalkOptions, walk


@dataclass
class ScanOptions:
    roots: List[str] = field(default_factory=list)
    mode: str = "probe"
    depth: int = defaults.DEFAULT_SCAN_DEPTH
    limit: int = defaults.DEFAULT_SCAN_LIMIT
    time_limit: int = defaults.DEFAULT_SCAN_TIME_LIMIT
    refresh: bool = False
    include_removable: bool = False
    include_network: bool = False


def _priority(platform: str) -> int:
    try:
        return defaults.PLATFORM_PRIORITY.index(platform)
    except ValueError:
        return len(defaults.PLATFORM_PRIORITY)


class ScannerService:
    def __init__(self, db, config) -> None:
        self.db = db
        self.config = config
        self.skills = SkillsRepo(db)
        self.scans = ScansRepo(db)

    def _root_mapping(self, options: ScanOptions) -> Tuple[List[Dict[str, str]], List[str]]:
        if options.mode == "full":
            if options.roots:
                mapping = []
                skipped = []
                for root in options.roots:
                    expanded = os.path.abspath(os.path.expanduser(str(root)))
                    if os.path.isdir(expanded):
                        mapping.append({"path": expanded, "platform": "disk", "exists": True})
                    else:
                        skipped.append(expanded)
                return mapping, skipped
            drives = select_drives(options.include_removable, options.include_network)
            return [{"path": item["path"], "platform": "disk", "exists": True} for item in drives], []
        if options.roots:
            mapping: List[Dict[str, str]] = []
            skipped: List[str] = []
            for root in options.roots:
                expanded = os.path.abspath(os.path.expanduser(str(root)))
                if os.path.isdir(expanded):
                    mapping.append({"path": expanded, "platform": "custom", "exists": True})
                else:
                    skipped.append(expanded)
            return mapping, skipped
        return detect_roots(extra_roots=self.config.roots), []

    def _load_existing(self) -> Tuple[Dict[str, Skill], Dict[str, Dict[str, Any]]]:
        rows = self.db.query_all("SELECT * FROM skills")
        by_real: Dict[str, Skill] = {str(row["real_path"]): Skill.from_row(row) for row in rows}
        by_id = {skill.id: skill for skill in by_real.values()}
        loc_rows = self.db.query_all("SELECT real_path, skill_id, mtime, size_bytes FROM skill_locations")
        loc_meta: Dict[str, Dict[str, Any]] = {}
        for row in loc_rows:
            real_path = str(row["real_path"])
            loc_meta[real_path] = {
                "skill_id": str(row["skill_id"]),
                "mtime": float(row["mtime"]),
                "size_bytes": int(row["size_bytes"]),
            }
            skill = by_id.get(str(row["skill_id"]))
            if skill is not None:
                by_real.setdefault(real_path, skill)
        return by_real, loc_meta

    def _parse_candidate(self, candidate: Dict[str, Any], existing: Optional[Skill]) -> Dict[str, Any]:
        path = candidate["path"]
        directory = os.path.dirname(path)
        now = utc_now_iso()
        try:
            document = read_document(path)
            markdown = parse_markdown(document.body)
            resources = enumerate_resources(directory)
            quality, details, warnings = score_quality(document, markdown, resources, directory_name_for(directory))
            content_hash = skill_dir_hash(directory)
            name = document.name() or os.path.basename(directory)
            description = document.description()
            dependencies = parse_dependencies(document.frontmatter, document.body, directory)
            size = document.file_size + sum(int(item["size_bytes"]) for item in resources)
            skill = Skill(
                id=existing.id if existing else short_id(content_hash, candidate["real_path"]),
                path=path,
                real_path=candidate["real_path"],
                name=name,
                description=description,
                body_preview=document.body[:512],
                search_blob=normalize_search(name + " " + description + " " + document.body),
                frontmatter_json=dumps(document.frontmatter),
                headings_json=dumps(markdown.headings),
                resources_json=dumps(resources),
                dependencies_json=dumps(dependencies),
                warnings_json=dumps(warnings),
                category=existing.category if existing else "未分类",
                category_source=existing.category_source if existing else "keyword",
                confidence=existing.confidence if existing else 0.0,
                platform_origin=candidate["platform"],
                size_bytes=size,
                lines=markdown.lines,
                chars=markdown.chars,
                mtime=float(candidate["mtime"]),
                content_hash=content_hash,
                quality_score=quality,
                quality_json=dumps(details),
                parse_error=document.parse_error,
                missing=0,
                first_seen=existing.first_seen if existing else now,
                last_seen=now,
            )
            return {"candidate": candidate, "skill": skill, "unchanged": False, "hash": content_hash}
        except Exception as exc:  # noqa: BLE001
            skill = self._unreadable_skill(candidate, existing, exc, now)
            return {"candidate": candidate, "skill": skill, "unchanged": False, "hash": skill.content_hash}

    def _unreadable_skill(self, candidate, existing, exc, now) -> Skill:
        unreadable_hash = "unreadable:" + candidate["real_path"]
        return Skill(
            id=existing.id if existing else short_id(unreadable_hash, candidate["real_path"]),
            path=candidate["path"],
            real_path=candidate["real_path"],
            name=existing.name if existing else os.path.basename(os.path.dirname(candidate["path"])),
            description=existing.description if existing else "",
            platform_origin=candidate["platform"],
            mtime=float(candidate["mtime"]),
            content_hash=unreadable_hash,
            parse_error=f"READ_FAILED: {exc}",
            quality_score=0,
            quality_json=dumps([{"code": "PARSE_FAILED", "delta": -40, "reason": str(exc)}]),
            missing=0,
            first_seen=existing.first_seen if existing else now,
            last_seen=now,
        )

    def _is_unchanged(
        self,
        candidate: Dict[str, Any],
        existing: Optional[Skill],
        refresh: bool,
        loc_meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if existing is None or refresh or existing.missing != 0 or existing.parse_error is not None:
            return False
        expected_mtime = float(loc_meta["mtime"]) if loc_meta else float(existing.mtime)
        if abs(float(candidate["mtime"]) - expected_mtime) >= 1e-6:
            return False
        if loc_meta and int(loc_meta["size_bytes"]) != int(candidate["size"]):
            return False
        return True

    def _collect(
        self,
        result,
        refresh: bool,
        cancel_token,
        progress,
        deadline: float,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        existing_by_real, loc_meta = self._load_existing()
        seen_real = set()
        entries: List[Dict[str, Any]] = []
        cancelled = result.cancelled
        total = len(result.candidates)
        for index, candidate in enumerate(result.candidates):
            if cancel_token is not None and cancel_token.is_set():
                cancelled = True
                break
            if time.monotonic() > deadline:
                result.accumulator.time_reached()
                break
            real_path = os.path.normcase(os.path.realpath(candidate["path"]))
            if real_path in seen_real:
                continue
            seen_real.add(real_path)
            candidate["real_path"] = real_path
            existing = existing_by_real.get(real_path)
            if self._is_unchanged(candidate, existing, refresh, loc_meta.get(real_path)):
                entry = {"candidate": candidate, "skill": existing, "unchanged": True, "hash": existing.content_hash}
            else:
                entry = self._parse_candidate(candidate, existing)
                result.accumulator.body_read()
                if existing is None:
                    result.accumulator.new()
                else:
                    result.accumulator.updated()
            entries.append(entry)
            if progress and (index % 50 == 0 or index == total - 1):
                progress("parse", index + 1, total, f"解析 {index + 1}/{total}")
        return entries, cancelled

    def _groups(self, entries: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for entry in entries:
            buckets.setdefault(str(entry["hash"]), []).append(entry)
        groups: List[List[Dict[str, Any]]] = []
        for hash_value in sorted(buckets):
            group = sorted(
                buckets[hash_value],
                key=lambda item: (_priority(str(item["candidate"]["platform"])), item["candidate"]["real_path"]),
            )
            existing = [item for item in group if item.get("skill") is not None]
            primary = existing[0] if existing else group[0]
            group.remove(primary)
            groups.append([primary] + group)
        return groups

    def _persist(
        self, groups: List[List[Dict[str, Any]]], progress, cancel_token
    ) -> Tuple[List[Dict[str, Any]], bool]:
        summaries: List[Dict[str, Any]] = []
        skills_batch: List[Skill] = []
        locations_batch: List[SkillLocation] = []
        cancelled = False
        now = utc_now_iso()

        def flush() -> None:
            nonlocal skills_batch, locations_batch
            if not skills_batch and not locations_batch:
                return
            self.skills.upsert_many(skills_batch, locations_batch)
            skills_batch = []
            locations_batch = []

        for index, group in enumerate(groups):
            if cancel_token is not None and cancel_token.is_set():
                cancelled = True
                break
            primary = group[0]
            skill = primary.get("skill")
            if skill is None:
                continue
            skill.last_seen = now
            skill.missing = 0
            if not primary["unchanged"]:
                skill.path = primary["candidate"]["path"]
                skill.real_path = primary["candidate"]["real_path"]
                skill.platform_origin = primary["candidate"]["platform"]
                skill.mtime = float(primary["candidate"]["mtime"])
                skills_batch.append(skill)
            locations_batch.extend(self._locations_for(group, skill.id, primary, now))
            summaries.append(self._summary_for(skill, group))
            if len(skills_batch) + len(locations_batch) >= defaults.BATCH_SIZE * 2:
                flush()
            if progress and (index % 25 == 0 or index == len(groups) - 1):
                progress("write", index + 1, len(groups), f"写入 {index + 1}/{len(groups)}")
        flush()
        return summaries, cancelled

    def _locations_for(self, group, skill_id: str, primary, now: str) -> List[SkillLocation]:
        result: List[SkillLocation] = []
        for entry in group:
            candidate = entry["candidate"]
            result.append(
                SkillLocation(
                    skill_id=skill_id,
                    path=candidate["path"],
                    real_path=candidate["real_path"],
                    platform=candidate["platform"],
                    is_primary=1 if entry is primary else 0,
                    mtime=float(candidate["mtime"]),
                    size_bytes=int(candidate["size"]),
                    last_seen=now,
                )
            )
        return result

    def _summary_for(self, skill: Skill, group) -> Dict[str, Any]:
        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "path": skill.path,
            "platform": skill.platform_origin,
            "size_bytes": skill.size_bytes,
            "lines": skill.lines,
            "quality_score": skill.quality_score,
            "category": skill.category,
            "copies": len(group),
        }

    def _mark_missing(self, seen_ids: set, roots: List[str]) -> int:
        missing_ids = []
        for skill_id, path, missing in self.skills.all_paths():
            if skill_id in seen_ids or missing:
                continue
            if any(is_within(path, root) for root in roots):
                missing_ids.append(skill_id)
        return self.skills.mark_missing(missing_ids)

    def _empty_result(self, scan_id: int, opts: ScanOptions, skipped_roots: List[str]) -> Dict[str, Any]:
        accumulator = ScanAccumulator()
        self.scans.finish(scan_id, utc_now_iso(), accumulator.stats, [])
        return {
            "scan_id": scan_id,
            "mode": opts.mode,
            "roots": [],
            "skipped_roots": skipped_roots,
            "stats": accumulator.to_dict(),
            "items": [],
            "cancelled": False,
            "coverage": [],
        }

    def scan(
        self,
        job_id: Optional[str] = None,
        options: ScanOptions = None,
        cancel_token: Any = None,
        progress: Optional[Callable[[str, int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        opts = options or ScanOptions()
        started_iso = utc_now_iso()
        started = time.monotonic()
        mapping, skipped_roots = self._root_mapping(opts)
        scan_id = self.scans.create(
            Scan(
                id=None,
                mode=opts.mode,
                roots_json=dumps([item["path"] for item in mapping]),
                started_at=started_iso,
                job_id=job_id,
                stats_json="{}",
                coverage_json="[]",
            )
        )
        if not mapping:
            return self._empty_result(scan_id, opts, skipped_roots)
        walk_progress = None
        if progress:
            def walk_progress(current: int, total: int, message: str) -> None:
                progress("walk", current, total, message)
        walk_options = WalkOptions(
            depth=opts.depth,
            limit=opts.limit,
            time_limit=opts.time_limit,
            prune_names=defaults.PRUNE_NAMES,
            ignore_rules=self.config.ignore_rules,
        )
        walk_result = walk(mapping, walk_options, cancel_token, walk_progress)
        deadline = started + opts.time_limit
        entries, cancelled_parse = self._collect(walk_result, opts.refresh, cancel_token, progress, deadline)
        groups = self._groups(entries)
        summaries, cancelled_write = self._persist(groups, progress, cancel_token)
        seen_ids = {entry["skill"].id for entry in entries if entry.get("skill") is not None}
        roots = [item["path"] for item in mapping]
        self._mark_missing(seen_ids, roots)
        cancelled = walk_result.cancelled or cancelled_parse or cancelled_write
        stats = walk_result.accumulator.to_dict()
        stats["dup_locations"] = max(0, sum(len(group) - 1 for group in groups))
        self.scans.finish(scan_id, utc_now_iso(), walk_result.accumulator.stats, walk_result.accumulator.uncovered_dirs)
        return {
            "scan_id": scan_id,
            "mode": opts.mode,
            "roots": roots,
            "skipped_roots": skipped_roots,
            "stats": stats,
            "items": summaries,
            "cancelled": cancelled,
            "coverage": walk_result.accumulator.uncovered_dirs,
        }