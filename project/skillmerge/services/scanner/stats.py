from __future__ import annotations

from typing import Any, Dict, List

from ...storage.models import ScanStats

MAX_SKIP_DETAILS = 200


class ScanAccumulator:
    def __init__(self) -> None:
        self.stats = ScanStats()
        self.skipped_details: List[Dict[str, str]] = []
        self.uncovered_dirs: List[str] = []
        self.prune_hits: Dict[str, int] = {}

    def directory_scanned(self) -> None:
        pass

    def found(self) -> None:
        self.stats.found += 1

    def new(self) -> None:
        self.stats.new += 1

    def updated(self) -> None:
        self.stats.updated += 1

    def body_read(self) -> None:
        self.stats.body_reads += 1

    def duplicate_location(self) -> None:
        self.stats.dup_locations += 1

    def permission_error(self, path: str, message: str) -> None:
        self.stats.skipped_permission += 1
        if len(self.skipped_details) < MAX_SKIP_DETAILS:
            self.skipped_details.append({"path": path, "reason": message})

    def pruned(self, name: str) -> None:
        self.stats.pruned += 1
        self.prune_hits[name] = self.prune_hits.get(name, 0) + 1

    def limit_reached(self, remaining: List[str]) -> None:
        self.stats.limit_hit = True
        self.uncovered_dirs = list(remaining[:500])

    def time_reached(self) -> None:
        self.stats.time_limit_hit = True

    def to_dict(self) -> Dict[str, Any]:
        data = self.stats.to_dict()
        data["prune_hits"] = dict(sorted(self.prune_hits.items()))
        data["skipped_details"] = list(self.skipped_details)
        return data