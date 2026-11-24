"""Upgrade check: three signals, seven states, declaration diff from fixtures."""
from __future__ import annotations

import json
from pathlib import Path

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
    data = _load()
    new = (data.get("repos") or {}).get(repo, {})
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
        "source": "fixture",
    }