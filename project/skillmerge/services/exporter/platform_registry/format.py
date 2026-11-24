from __future__ import annotations

from typing import Any, Dict, List


def _package(rule: Dict[str, Any]) -> Dict[str, Any]:
    package = rule.get("package")
    return package if isinstance(package, dict) else {}


def _install_scopes(rule: Dict[str, Any]) -> List[str]:
    install = rule.get("install")
    if not isinstance(install, dict):
        return []
    scopes = []
    for scope in ("global", "project"):
        value = install.get(scope)
        if isinstance(value, str) and value.strip():
            scopes.append(scope)
    return scopes


def _rule_source(entry) -> str:
    if entry.rule_body:
        return "verified"
    if entry.legacy_limits:
        return "legacy_limits"
    return "unknown"


def _rule_status(value: str) -> str:
    return "verified" if value == "verified" else "candidate"


def format_info(entry) -> Dict[str, Any]:
    rule = entry.as_rule()
    package = _package(rule)
    if entry.kind == "prompt":
        package_type = "prompt"
        skill_md_path = "prompt.md"
    else:
        package_type = str(package.get("type") or "unknown")
        skill_md_path = str(package.get("skill_md_path") or "SKILL.md")
    scopes = _install_scopes(rule)
    source = _rule_source(entry)
    return {
        "package_type": package_type,
        "wrap": bool(package.get("wrap", False)),
        "skill_md_path": skill_md_path,
        "install_scopes": scopes,
        "rule_source": source,
        "rule_status": _rule_status(entry.verification_status),
        "requires_confirm": entry.verification_status == "unknown",
        "limits_source": source,
    }


def manifest_format(rule: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(rule.get("kind") or "skill")
    package = _package(rule)
    if kind == "prompt":
        package_type = "prompt"
        skill_md_path = "prompt.md"
    else:
        package_type = str(package.get("type") or "unknown")
        skill_md_path = str(package.get("skill_md_path") or "SKILL.md")
    scopes = _install_scopes(rule)
    status = str(rule.get("verification_status") or "unknown")
    limits_source = str(rule.get("limits_source") or "")
    if not limits_source:
        limits_source = "verified" if status == "verified" else "legacy_limits"
    return {
        "package_type": package_type,
        "wrap": bool(package.get("wrap", False)),
        "skill_md_path": skill_md_path,
        "rule_status": _rule_status(status),
        "limits_source": limits_source,
        "install_available": bool(scopes),
    }