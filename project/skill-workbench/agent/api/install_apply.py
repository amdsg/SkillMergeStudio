"""install/apply: capability gate, sandbox path, plan binding, backup and rollback."""
from __future__ import annotations

import json
from pathlib import Path

from agent.config.defaults import RISK_ACK_VERSION
from agent.config.runtime import is_enabled
from agent.core import atomic_write, backup, rollback
from agent.core.hashing import sha256_text
from agent.core.paths import data_dir
from agent.core.records import append
from agent.http.errors import DomainError

SANDBOX = data_dir() / "sandbox"
BACKUPS = data_dir() / "backups"


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def confirm_token(plan_hash: str) -> str:
    return sha256_text(f"{plan_hash}|{RISK_ACK_VERSION}")[:16]


def _validate(payload: dict) -> tuple[Path, list[dict], str]:
    if not is_enabled("real_write"):
        raise DomainError("E_CAPABILITY_DISABLED", "wb.error.capability_disabled", status=403,
                          params={"capability": "real_write"}, fix_key="wb.fix.enable_capability")
    target = Path(str(payload.get("target_path", ""))).resolve()
    if not target.is_relative_to(SANDBOX.resolve()):
        raise DomainError("E_PATH_DENIED", "wb.error.path_denied", status=403,
                          params={"path": str(target)}, fix_key="wb.fix.check_path")
    files = payload.get("files") or []
    if not files or not all(isinstance(item, dict) and "path" in item and "content" in item for item in files):
        raise DomainError("E_BAD_REQUEST", "wb.error.bad_request", status=400,
                          params={"fields": ["files"]}, fix_key="wb.fix.check_input")
    plan_hash = str(payload.get("plan_hash", ""))
    if str(payload.get("confirm_token", "")) != confirm_token(plan_hash):
        raise DomainError("E_CONFIRM_REQUIRED", "wb.error.confirm_required", status=403,
                          params={"plan_hash": plan_hash}, fix_key="wb.fix.confirm_risk")
    return target, files, plan_hash


def apply_endpoint(params, body, request_id):
    payload = _body(body)
    target, files, plan_hash = _validate(payload)
    relative_paths = [str(item["path"]) for item in files]
    manifest = backup.create(BACKUPS, target, relative_paths)
    created_hashes = {}
    try:
        for item in files:
            destination = target / str(item["path"])
            created_hashes[str(item["path"])] = sha256_text(str(item["content"]))
            atomic_write.write_text(destination, str(item["content"]))
        for item in files:
            destination = target / str(item["path"])
            if sha256_text(destination.read_text(encoding="utf-8")) != created_hashes[str(item["path"])]:
                raise OSError(f"verify failed: {item['path']}")
    except Exception as error:  # noqa: BLE001 - rollback is the contract
        result = rollback.rollback(manifest, target, created_hashes)
        append("installs", {"state": "failed" if result["ok"] else "rollback_failed", "plan_hash": plan_hash, "error": str(error)[:120]})
        if not result["ok"]:
            raise DomainError("E_ROLLBACK_FAILED", "wb.error.rollback_failed", status=500,
                              params={"errors": result["errors"]}, fix_key="wb.fix.view_diagnostics") from error
        raise DomainError("E_WRITE_FAILED", "wb.error.write_failed", status=500,
                          params={"reason": str(error)[:120]}, fix_key="wb.fix.retry_later") from error
    append("installs", {"state": "succeeded", "plan_hash": plan_hash, "files": relative_paths})
    return {"state": "succeeded", "plan_hash": plan_hash, "files": relative_paths, "backup_id": manifest["backup_id"], "writes": len(files)}