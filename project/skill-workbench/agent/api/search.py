"""Search over skill repositories: fixture by default, live GitHub when enabled."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent.net.live import get_client, is_live

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
    if is_live():
        return _search_github(query, sort, page, get_client())
    return _search_fixture(query, sort, page)


def _search_fixture(query: str, sort: str, page: int) -> dict:
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


def _search_github(query: str, sort: str, page: int, client) -> dict:
    params = {"q": query or "skill", "per_page": "10", "page": str(page)}
    gh_sort = {"stars": "stars", "updated": "updated"}.get(sort)
    if gh_sort:
        params["sort"] = gh_sort
    result = client.request("GET", "/search/repositories", params)
    raw_items = (result.get("data") or {}).get("items") or []
    meta = result.get("meta") or {}
    return {
        "items": [_map_github_item(item) for item in raw_items],
        "page": page,
        "quota": {"remaining": meta.get("remaining"), "reset_at": meta.get("reset_at"), "source": "github"},
        "cache": {"hit": False, "ttl_seconds": 300},
    }


def _map_github_item(item: dict) -> dict:
    return {
        "full_name": item.get("full_name"),
        "description": item.get("description"),
        "stars": item.get("stargazers_count"),
        "pushed_at": item.get("pushed_at"),
        "release_tag": "unknown",
        "release_download": "unknown",
        "commit_sha": "unknown",
        "topics": item.get("topics") or [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "factors": {},
        "factor_weights_version": FACTOR_WEIGHTS_VERSION,
        "missing_factors": ["release_tag", "release_download", "commit_sha"],
        "applicability": {"mode": "unknown", "targets": [], "reason_code": "not_fetched"},
        "source": "github",
    }

def search_endpoint(params, body, request_id):
    payload = json.loads(body.decode("utf-8")) if body else {}
    if not isinstance(payload, dict):
        payload = {}
    return search(payload)