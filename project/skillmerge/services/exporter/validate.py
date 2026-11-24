from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..parser.markdown import parse_markdown
from .namer import forbidden_hits

RULE_STALE_DAYS = 90
RULE_STRONG_DAYS = 180
BINARY_EXT = (".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".com", ".scr")
MAX_BINARY = 10 * 1024 * 1024


def _check(check_id: str, level: str, message: str, fix: str, phase: str) -> Dict[str, str]:
    return {"id": check_id, "level": level, "message": message, "fix": fix, "phase": phase}


def _age_days(value: str) -> int:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 9999
    return (datetime.now(timezone.utc) - parsed).days


def _name_checks(rule: Dict[str, Any], spec: Dict[str, Any], phase: str) -> List[Dict[str, str]]:
    checks = []
    name = str(spec.get("name", ""))
    pattern = str(rule["name"]["pattern"])
    maximum = int(rule["name"]["max_length"])
    if not re.fullmatch(pattern, name):
        checks.append(_check("V-NAME-01", "error", f"名称不符合规则：{pattern}", "使用小写字母、数字与连字符", phase))
    if len(name) > maximum:
        checks.append(_check("V-NAME-01", "error", f"名称超过 {maximum} 字符", f"缩短到 {maximum} 字符以内", phase))
    hits = forbidden_hits(name, rule)
    if hits:
        checks.append(
            _check("V-NAME-01", "error", f"名称含保留词：{', '.join(hits)}", f"替换保留词，例如 x-{name.replace(hits[0], 'helper')}", phase)
        )
    expected = str(spec.get("layout_name", ""))
    if expected and spec.get("mode") in ("zip", "install", "download") and expected != name:
        checks.append(
            _check("V-NAME-02", "error", f"目录/zip 顶层为 {expected}，与名称 {name} 不一致", "将输出目录名改为与 name 一致", phase)
        )
    return checks


def _content_checks(rule: Dict[str, Any], spec: Dict[str, Any], phase: str) -> List[Dict[str, str]]:
    checks = []
    text = str(spec.get("text", ""))
    description = str(spec.get("description", ""))
    if len(description) > int(rule["description"]["max_chars"]):
        checks.append(
            _check("V-DESC-01", "error", "描述超过平台上限", f"重写为 ≤{rule['description']['max_chars']} 字符", phase)
        )
    lines = text.split("\n")
    if len(lines) > int(rule["skill_md"]["max_lines"]):
        checks.append(_check("V-MD-01", "error", "SKILL.md 行数超限", "按裁剪建议移除低优先级章节", phase))
    if len(text.encode("utf-8")) > int(rule["skill_md"]["max_bytes"]):
        checks.append(_check("V-MD-02", "error", "SKILL.md 字节数超限", "移除低优先级章节或资源", phase))
    heading_count = sum(1 for line in lines if line.startswith("# "))
    body = text.split("\n---\n", 1)[-1] if "\n---\n" in text else text
    if rule.get("kind") == "prompt":
        if not text.strip():
            checks.append(_check("V-MD-03", "error", "提示词正文为空", "重新生成提示词包", phase))
    elif heading_count != 1 or not body.strip():
        checks.append(_check("V-MD-03", "error", "一级标题必须唯一且正文非空", "保留一个 # 标题并确保正文非空", phase))
    required = list(rule["frontmatter"].get("required", []))
    fm = spec.get("frontmatter") or {}
    missing = [key for key in required if not str(fm.get(key, "")).strip()]
    if missing:
        checks.append(_check("V-FM-01", "error", f"frontmatter 缺少必填字段：{', '.join(missing)}", "补齐必填字段后重试", phase))
    return checks


def _bundle_checks(rule: Dict[str, Any], spec: Dict[str, Any], phase: str) -> List[Dict[str, str]]:
    checks = []
    files = list(spec.get("files", []))
    total = sum(int(item.get("size_bytes", 0)) for item in files)
    limit_bytes = int(rule["bundle"]["max_mb"]) * 1024 * 1024
    if limit_bytes and total > limit_bytes:
        checks.append(_check("V-BUNDLE-01", "error", "产物总大小超过平台上限", "裁剪资源或移除大文件", phase))
    if len(files) > int(rule["bundle"]["max_files"]):
        checks.append(_check("V-BUNDLE-02", "error", "文件数超过平台上限", "移除低优先级资源", phase))
    single = int(rule["bundle"]["max_file_mb"]) * 1024 * 1024
    oversized = [str(item.get("rel_path")) for item in files if single and int(item.get("size_bytes", 0)) > single]
    if oversized:
        checks.append(_check("V-BUNDLE-03", "error", f"单文件超限：{oversized[:3]}", "压缩或移除超限文件", phase))
    return checks


def _rule_checks(rule: Dict[str, Any], phase: str) -> List[Dict[str, str]]:
    checks = []
    status = str(rule.get("verification_status", ""))
    evidence = str(rule.get("evidence_level", ""))
    source = str(rule.get("source", "unknown"))
    verified = str(rule.get("verified_at", "unknown"))
    if evidence in ("failed_unreachable", "no_evidence", "discovery_source"):
        checks.append(_check("V-RULE-04", "error", "不可达/发现源对象不能作为平台导出", "从平台清单选择可导出的条目", phase))
        return checks
    if status == "unknown" or source.lower() == "unknown" or verified.lower() == "unknown":
        label = "候选（有 SKILL.md 证据）" if evidence == "candidate_skill" else "候选（规则机制未核验）"
        checks.append(_check("V-RULE-02", "warn", f"{label}，规则未核验", "导出前请核对官方文档，风险自负", phase))
        if rule.get("last_verified_at"):
            checks.append(_check("V-RULE-03", "warn", "来源可能失效，保留最后一次核验日期", "重新访问 source 并人工复核", phase))
        if rule.get("limits_source") == "legacy_limits":
            checks.append(_check("V-RULE-05", "warn", "候选限制值未核验，preflight 使用保守兜底", "确认导出结果符合目标平台要求", phase))
        return checks
    age = _age_days(verified)
    if age >= RULE_STALE_DAYS:
        level = "warn"
        message = f"平台规则核验于 {verified}，已超过 {RULE_STALE_DAYS} 天"
        if age >= RULE_STRONG_DAYS:
            message = f"平台规则核验于 {verified}，已超过 {RULE_STRONG_DAYS} 天，请务必核对官网"
        checks.append(_check("V-RULE-01", level, message, "访问规则 source 重新核验后更新 verified_at", phase))
    return checks


def _asset_checks(spec: Dict[str, Any], phase: str) -> List[Dict[str, str]]:
    suspicious = []
    for item in spec.get("files", []):
        rel = str(item.get("rel_path", "")).lower()
        if rel.endswith(BINARY_EXT) or (str(item.get("kind")) == "binary" and int(item.get("size_bytes", 0)) > MAX_BINARY):
            suspicious.append(str(item.get("rel_path")))
    if suspicious:
        return [_check("V-ASSET-01", "warn", f"可疑二进制资源：{suspicious[:3]}", "确认来源并考虑移除，避免触发平台安全扫描", phase)]
    return []


def _zip_plan_checks(spec: Dict[str, Any], phase: str) -> List[Dict[str, str]]:
    checks = []
    prefix = str(spec.get("expected_prefix", ""))
    entries = list(spec.get("planned_entries", []))
    if prefix:
        if prefix.startswith("/") or ".." in prefix.split("/") or ":" in prefix:
            checks.append(_check("V-ZIP-01", "error", "zip 顶层前缀非法", "使用相对路径前缀", phase))
        top = prefix.rstrip("/").split("/")[0]
        expected = str(spec.get("layout_name", ""))
        if expected and top not in (expected, "skills"):
            checks.append(_check("V-ZIP-01", "error", f"zip 顶层为 {top}，期望包含 {expected}", f"调整结构为 {prefix}SKILL.md", phase))
    for rel in entries:
        if rel.startswith("/") or ".." in rel.split("/") or re.match(r"^[A-Za-z]:", rel):
            checks.append(_check("V-ZIP-02", "error", f"zip 条目路径非法：{rel}", "重新打包并规范化路径", phase))
    return checks


def _zip_actual_checks(zip_path: str, spec: Dict[str, Any]) -> List[Dict[str, str]]:
    checks = []
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return [_check("V-ZIP-01", "error", "zip 无法读取", "重新打包", "post")]
    expected_prefix = str(spec.get("expected_prefix", ""))
    for name in names:
        if name.startswith("/") or ".." in name.split("/") or re.match(r"^[A-Za-z]:", name):
            checks.append(_check("V-ZIP-02", "error", f"zip 条目路径非法：{name}", "重新打包", "post"))
        if not name.startswith(expected_prefix):
            checks.append(_check("V-ZIP-01", "error", f"zip 条目不在期望前缀 {expected_prefix} 下：{name}", "调整 zip 顶层结构", "post"))
    return checks


def dedupe_checks(checks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    result = []
    for item in checks:
        key = (item["id"], item["phase"], item["message"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=lambda item: (item["id"], item["phase"], item["message"]))


def run_preflight(rule: Dict[str, Any], spec: Dict[str, Any]) -> List[Dict[str, str]]:
    checks = []
    checks.extend(_name_checks(rule, spec, "pre"))
    checks.extend(_content_checks(rule, spec, "pre"))
    checks.extend(_bundle_checks(rule, spec, "pre"))
    checks.extend(_rule_checks(rule, "pre"))
    checks.extend(_asset_checks(spec, "pre"))
    if rule["package"]["type"] == "zip" or spec.get("mode") in ("zip", "download"):
        checks.extend(_zip_plan_checks(spec, "pre"))
    return dedupe_checks(checks)


def run_postflight(rule: Dict[str, Any], spec: Dict[str, Any], zip_path: Optional[str] = None) -> List[Dict[str, str]]:
    checks = []
    checks.extend(_name_checks(rule, spec, "post"))
    checks.extend(_content_checks(rule, spec, "post"))
    checks.extend(_bundle_checks(rule, spec, "post"))
    checks.extend(_rule_checks(rule, "post"))
    checks.extend(_asset_checks(spec, "post"))
    if zip_path:
        checks.extend(_zip_actual_checks(zip_path, spec))
    return dedupe_checks(checks)


def errors(checks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [item for item in checks if item["level"] == "error"]