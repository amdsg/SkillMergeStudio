"""Deterministic search over fixture repository metadata.

Real GitHub calls are intentionally not performed here: use fixtures for automated
evidence and treat live network results as manual evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests_wb" / "fixtures" / "search" / "repos.json"
FACTOR_WEIGHTS_VERSION = "wb-factors-v1"


def _load_items() -> list[dict]:
    try:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _score(item: dict) -> tuple:
    stars = int(item.get("stars") or 0)
    pushed_at = str(item.get("pushed_at") or "")
    has_release = bool(item.get("release_tag"))
    return (has_release, stars, pushed_at, str(item.get("full_name", "")))


def _query_matches(item: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join([
        str(item.get("full_name", "")),
        str(item.get("description", "")),
        " ".join(item.get("topics") or []),
    ]).lower()
    return query.lower() in haystack


def search(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    sort = str(payload.get("sort", "relevance"))
    page = int(payload.get("page", 1) or 1)
    items = [item for item in _load_items() if _query_matches(item, query)]
    if sort == "stars":
        items.sort(key=lambda item: int(item.get("stars") or 0), reverse=True)
    elif sort == "updated":
        items.sort(key=lambda item: str(item.get("pushed_at") or ""), reverse=True)
    else:
        items.sort(key=_score, reverse=True)
    items = items[(page - 1) * 10: page * 10]
    return {
        "items": [
            {
                "full_name": item.get("full_name"),
                "description": item.get("description"),
                "stars": item.get("stars"),
                "pushed_at": item.get("pushed_at"),
                "release_tag": item.get("release_tag") or "unknown",
                "release_download": item.get("release_download") or "unknown",
                "commit_sha": item.get("commit_sha"),
                "topics": item.get("topics") or [],
                "fetched_at": item.get("fetched_at"),
                "factors": item.get("factors") or {},
                "factor_weights_version": FACTOR_WEIGHTS_VERSION,
                "missing_factors": item.get("missing_factors") or [],
                "applicability": {
                    "mode": "unknown",
                    "targets": [],
                    "reason_code": "not_fetched",
                },
                "source": "fixture",
            }
            for item in items
        ],
        "page": page,
        "quota": {"remaining": None, "reset_at": None, "source": "fixture"},
        "cache": {"hit": False, "ttl_seconds": 300},
    }

def search_endpoint(params, body, request_id):
    payload = json.loads(body.decode("utf-8")) if body else {}
    if not isinstance(payload, dict):
        payload = {}
    return search(payload)