"""Dependency plan: source trace, hard limits, GitHub-only, cancellable, zero network."""
from __future__ import annotations

from collections import deque
import re

from agent.http.errors import DomainError

DEPTH_LIMIT = 2
TOTAL_LIMIT = 20
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _is_github(repo: str) -> bool:
    return bool(REPO_RE.match(repo or ""))


def build_plan(root: dict) -> dict:
    """Build a BFS fetch plan from one root manifest. Never performs network IO."""
    root_repo = str(root.get("repo_full_name", ""))
    root_id = str(root.get("skill_id", root_repo))
    declaration = root.get("fields") or root.get("declaration") or {}
    deps = declaration.get("dependencies") if isinstance(declaration, dict) else None
    if not isinstance(deps, list):
        deps = []
    plan = []
    denied = []
    truncated = False
    seen = {root_repo}
    queue = deque()
    for item in deps:
        repo = str(item.get("repo", "")) if isinstance(item, dict) else str(item)
        ref = str(item.get("ref", "unknown")) if isinstance(item, dict) else "unknown"
        queue.append({"repo": repo, "depth": 1, "parent": root_id, "declared_in": "manifest.dependencies", "ref": ref})
    while queue:
        node = queue.popleft()
        if not _is_github(node["repo"]):
            denied.append({"repo": node["repo"], "code": "E_DEPENDENCY_SOURCE_DENIED", "parent": node["parent"]})
            continue
        if node["depth"] > DEPTH_LIMIT:
            continue
        if node["repo"] in seen:
            continue
        if len(plan) >= TOTAL_LIMIT:
            truncated = True
            continue
        seen.add(node["repo"])
        plan.append({
            "repo": node["repo"],
            "ref": node["ref"],
            "depth": node["depth"],
            "parent_skill_id": node["parent"],
            "declared_in": node["declared_in"],
            "action": "fetch",
        })
    return {
        "root": root_repo,
        "items": plan,
        "denied": denied,
        "truncated": truncated,
        "limits": {"depth": DEPTH_LIMIT, "total": TOTAL_LIMIT, "same_repo_once": True},
        "count": len(plan),
    }


def execute(plan: dict, fetch, cancelled=None) -> dict:
    """Execute a plan with a caller-provided fetcher. Cancellation leaves zero partial output."""
    completed = []
    failed = []
    cancelled_flag = False
    for item in plan.get("items", []):
        if cancelled is not None and cancelled():
            cancelled_flag = True
            break
        try:
            result = fetch(item)
            completed.append({"repo": item["repo"], "result": result})
        except Exception as error:  # noqa: BLE001 - failure isolation is the contract
            failed.append({"repo": item["repo"], "code": getattr(error, "code", "E_INTERNAL")})
    return {
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled_flag,
        "dependencies_partial": bool(failed),
    }