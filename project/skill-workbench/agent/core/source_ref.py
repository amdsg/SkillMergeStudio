"""Source reference contract: six fields, missing values become unknown."""
from __future__ import annotations

from datetime import datetime, timezone


def build(repo_full_name: str, commit_sha: str = "", release_tag: str = "",
          pushed_at: str = "", archive_hash: str = "", content_hash: str = "") -> dict:
    return {
        "repo_full_name": repo_full_name or "unknown",
        "commit_sha": commit_sha or "unknown",
        "release_tag": release_tag or "unknown",
        "pushed_at": pushed_at or "unknown",
        "archive_hash": archive_hash or "unknown",
        "content_hash": content_hash or "unknown",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def validate(ref: dict) -> list[str]:
    missing = [key for key in ("commit_sha", "archive_hash") if str(ref.get(key, "unknown")) == "unknown"]
    return missing