"""Target-to-tool recommendation: exact hints join detected tools only."""
from __future__ import annotations

MATCHED_DETECTED = "matched_detected"
NO_TOOL_HINT = "no_tool_hint"
NO_DETECTED_TOOL = "no_detected_tool"
TOOL_EVIDENCE_UNKNOWN = "tool_evidence_unknown"
REASONS = (MATCHED_DETECTED, NO_TOOL_HINT, NO_DETECTED_TOOL, TOOL_EVIDENCE_UNKNOWN)


def recommend(target_id: str, hints: list[dict], tools: list[dict]) -> dict:
    entry = next((item for item in hints if item.get("target_id") == target_id), None)
    if entry is None:
        return {"recommended_tool_id": None, "reason_code": NO_TOOL_HINT, "candidates": []}
    hint_ids = list(entry.get("tool_ids") or [])
    if not hint_ids:
        return {"recommended_tool_id": None, "reason_code": NO_TOOL_HINT, "candidates": []}
    by_id = {str(tool.get("tool_id")): tool for tool in tools}
    known = [by_id[tool_id] for tool_id in hint_ids if tool_id in by_id]
    if not known:
        return {"recommended_tool_id": None, "reason_code": TOOL_EVIDENCE_UNKNOWN, "candidates": []}
    if all(str(tool.get("state", "unknown")) == "unknown" for tool in known):
        return {"recommended_tool_id": None, "reason_code": TOOL_EVIDENCE_UNKNOWN, "candidates": []}
    detected = [tool for tool in known if tool.get("state") == "detected"]
    if not detected:
        return {"recommended_tool_id": None, "reason_code": NO_DETECTED_TOOL, "candidates": []}
    detected.sort(key=lambda tool: (str(tool.get("matched_path", "")) == "", str(tool.get("tool_id", ""))))
    return {
        "recommended_tool_id": str(detected[0].get("tool_id")),
        "reason_code": MATCHED_DETECTED,
        "candidates": [str(tool.get("tool_id")) for tool in detected],
    }