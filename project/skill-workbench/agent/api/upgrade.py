"""Upgrade check: three signals, seven states, declaration diff.

Fixture-backed by default; live GitHub when enabled via agent.net.live.
"""
from __future__ import annotations

import json
from pathlib import Path

from agent.http.errors import DomainError
from agent.net.live import get_client, is_live

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests_wb" / "fixtures" / "upgrade" / "repos.json"


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _load() -> dict:
    try:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _compare(old: dict, new: dict) -> str:
    signals = ("commit_sha", "release_tag", "pushed_at")
    known = [signal for signal in signals if str(old.get(signal, "unknown")) != "unknown" and str(new.get(signal, "unknown")) != "unknown"]
    if not known:
        return "unknown"
    for signal in signals:
        if str(old.get(signal, "unknown")) == "unknown" or str(new.get(signal, "unknown")) == "unknown":
            continue
        if str(new.get(signal)) != str(old.get(signal)):
            return "has_update"
    return "up_to_date"


def check_endpoint(params, body, request_id):
    payload = _body(body)
    repo = str(payload.get("repo_full_name", ""))
    old = payload.get("local_ref") if isinstance(payload.get("local_ref"), dict) else {}
    if is_live():
        new = _fetch_github_ref(repo, get_client())
        source = "github"
    else:
        new = (_load().get("repos") or {}).get(repo, {})
        source = "fixture"
    return _build_result(repo, old, new, source)


def _build_result(repo: str, old: dict, new: dict, source: str) -> dict:
    state = _compare(old, new)
    old_decl = old.get("declaration")
    new_decl = new.get("declaration") if isinstance(new, dict) else None
    if old_decl is None:
        declaration_diff = {
            "legacy_missing": True,
            "added": [],
            "removed": [],
            "changed": [],
            "mode_change": None,
            "unchanged": False,
        }
    else:
        old_targets = set(old_decl.get("targets") or [])
        new_targets = set(new_decl.get("targets") or []) if isinstance(new_decl, dict) else set()
        declaration_diff = {
            "legacy_missing": False,
            "added": sorted(new_targets - old_targets),
            "removed": sorted(old_targets - new_targets),
            "changed": [],
            "mode_change": None if not new_decl else {"from": old_decl.get("mode"), "to": new_decl.get("mode")},
            "unchanged": old_targets == new_targets,
        }
    reason_key = "wb.reason.cannot_compare" if state == "unknown" else ""
    return {
        "repo_full_name": repo,
        "state": state,
        "reason_key": reason_key,
        "signals": {
            "commit_sha": {"old": old.get("commit_sha", "unknown"), "new": new.get("commit_sha", "unknown")},
            "release_tag": {"old": old.get("release_tag", "unknown"), "new": new.get("release_tag", "unknown")},
            "pushed_at": {"old": old.get("pushed_at", "unknown"), "new": new.get("pushed_at", "unknown")},
        },
        "declaration_diff": declaration_diff,
        "source": source,
    }


def _fetch_github_ref(repo: str, client) -> dict:
    ref = {"commit_sha": "unknown", "release_tag": "unknown", "pushed_at": "unknown", "declaration": None}
    if not repo or "/" not in repo:
        return ref
    owner, name = repo.split("/", 1)
    try:
        detail = client.request("GET", f"/repos/{owner}/{name}")
        ref["pushed_at"] = (detail.get("data") or {}).get("pushed_at", "unknown")
    except DomainError:
        pass
    try:
        commits = client.request("GET", f"/repos/{owner}/{name}/commits", {"per_page": "1"})
        items = (commits.get("data") or []) or []
        if items:
            ref["commit_sha"] = items[0].get("sha", "unknown")
    except DomainError:
        pass
    try:
        releases = client.request("GET", f"/repos/{owner}/{name}/releases", {"per_page": "1"})
        items = (releases.get("data") or []) or []
        if items:
            ref["release_tag"] = items[0].get("tag_name", "unknown")
    except DomainError:
        pass
    return ref