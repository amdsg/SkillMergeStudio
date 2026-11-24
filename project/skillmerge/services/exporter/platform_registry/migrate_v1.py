from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

RULE_BODY_FIELDS = ("name", "description", "skill_md", "bundle", "package", "frontmatter", "install")
GROUP_MAP = {
    "generic": "通用",
    "agent-skills": "通用",
    "claude": "Claude 生态",
    "codex": "OpenAI 生态",
    "chatgpt": "OpenAI 生态",
    "cursor": "IDE 集成",
    "copilot": "IDE 集成",
    "windsurf": "IDE 集成",
    "trae": "IDE 集成",
    "qoder": "IDE 集成",
    "roo": "IDE 集成",
    "cline": "IDE 集成",
    "antigravity": "IDE 集成",
    "codebuddy": "IDE 集成",
    "qwen": "国产大模型",
    "kimi": "国产大模型",
    "doubao": "国产大模型",
    "iflow": "国产大模型",
    "volcengine-ark": "国产大模型",
    "coze": "企业协作",
    "dingtalk-wukong": "企业协作",
    "dingtalk-expert": "企业协作",
    "workbuddy": "企业协作",
    "workbuddy-local": "企业协作",
    "gemini-cli": "开源 Agent",
    "opencode": "开源 Agent",
    "goose": "开源 Agent",
    "prompt-only": "提示词类",
}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _date_or_none(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.lower() == "unknown":
        return None
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return text
    except ValueError:
        return None


def _source_or_none(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return None if not text or text.lower() == "unknown" else text


def _body(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {key: raw[key] for key in RULE_BODY_FIELDS if key in raw and raw[key] is not None}


def normalize_v1(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(raw)
    source = _source_or_none(raw.get("source"))
    verified_at = _date_or_none(raw.get("verified_at"))
    verified = source is not None and verified_at is not None
    if source is None:
        source_type = "official_docs"
    elif source.startswith("local://"):
        source_type = "local_contract"
    else:
        source_type = "official_docs"
    body = _body(raw)
    legacy = None
    if not verified and body:
        legacy = body
    unknown_fields: List[str] = []
    if not verified:
        unknown_fields = sorted(body.keys()) if body else list(RULE_BODY_FIELDS)
        for field in RULE_BODY_FIELDS:
            data[field] = None
    data["rule_schema_version"] = 2
    data["group"] = raw.get("group") or GROUP_MAP.get(str(raw.get("id", "")), "通用")
    data["origin"] = "baseline"
    data["batch"] = "baseline"
    data["source"] = source
    data["source_type"] = source_type
    data["verification_status"] = "verified" if verified else "unknown"
    data["evidence_level"] = "verified" if verified else "candidate_rules"
    data["verified_at"] = verified_at if verified else None
    data["last_verified_at"] = verified_at if verified else None
    data["unknown_fields"] = unknown_fields
    data["aliases"] = list(raw.get("aliases") or [])
    data["legacy_limits"] = legacy
    notes = str(raw.get("notes") or "").strip()
    if not verified and "v1 兼容读取" not in notes:
        suffix = f"v1 兼容读取：无官方来源，未升级（{_today()}）。"
        notes = f"{notes}；{suffix}" if notes else suffix
    data["notes"] = notes
    return data


def normalize_v2(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(raw)
    source = data.get("source")
    verified_at = data.get("verified_at")
    if str(source or "").strip().lower() == "unknown":
        data["source"] = None
        source = None
    if str(verified_at or "").strip().lower() == "unknown":
        data["verified_at"] = None
        verified_at = None
    if not data.get("last_verified_at") and data.get("verification_status") == "verified":
        data["last_verified_at"] = verified_at
    if "legacy_limits" not in data:
        data["legacy_limits"] = None
    if "unknown_fields" not in data:
        data["unknown_fields"] = []
    if "aliases" not in data:
        data["aliases"] = []
    return data