"""Source text -> intermediate document plus a three-class mapping report."""
from __future__ import annotations

import re
import uuid

from agent.core.hashing import sha256_text
from agent.core.import_detect import load_profiles
from agent.core.intermediate import load_schema
from agent.core.manifest import _frontmatter

HEADING = re.compile(r"^##\s+(.+)$", re.M)
NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+(.+)$", re.M)
KNOWN_MANIFEST = {"native_targets", "capability_tags", "version", "dependencies"}
DEFAULT_KEYWORDS = {
    "capabilities": ["Capabilities", "Skills"],
    "instructions": ["Instructions", "Steps"],
}


def _keywords(profile_id: str) -> dict:
    profile = next((item for item in load_profiles() if item.get("profile_id") == profile_id), None)
    return (profile or {}).get("section_keywords") or DEFAULT_KEYWORDS


def _summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    return lines[0] if lines else "unknown"


def _name(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else "unknown"


def _section(text: str, keywords: tuple[str, ...]) -> str:
    blocks = {}
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1).strip()] = text[start:end]
    for title, body in blocks.items():
        if any(keyword.lower() in title.lower() for keyword in keywords):
            return body
    return ""


def _capabilities(body: str) -> list[dict]:
    items = [line.strip("-* \t") for line in body.splitlines() if line.strip().startswith(("-", "*"))]
    if not items:
        return []
    return [{"trigger": item, "inputs": [], "outputs": [], "constraints": []} for item in items]


def _instructions(text: str, body: str) -> list[dict]:
    lines = [match.group(2).strip() for match in NUMBERED.finditer(body)] or [
        match.group(2).strip() for match in NUMBERED.finditer(text)
    ]
    return [{"step": index, "text": line} for index, line in enumerate(lines, 1)]


def build(text: str, profile_id: str, recognized: bool, source: str = "unknown",
          import_id: str = "", overrides: dict | None = None) -> tuple[dict, dict]:
    overrides = overrides or {}
    import_id = import_id or uuid.uuid4().hex[:12]
    report_id = f"import-report:{import_id}"
    mapped = []
    dropped = []
    synthesized = []

    def add_synth(path: str, value: str = "unknown", origin: str = "unknown"):
        synthesized.append({"target_path": path, "value": value, "origin": origin})

    name = _name(text)
    if name != "unknown":
        mapped.append({"source_path": "h1", "target_path": "identity.name", "value_sha256": sha256_text(name)})
    else:
        add_synth("identity.name")

    summary = _summary(text)
    if summary != "unknown":
        mapped.append({"source_path": "first_paragraph", "target_path": "intent.summary", "value_sha256": sha256_text(summary)})
    else:
        add_synth("intent.summary")

    version = overrides.get("identity.version", "unknown")
    if version == "unknown":
        add_synth("identity.version")
    else:
        synthesized.append({"target_path": "identity.version", "value": version, "origin": "user_input"})

    keywords = _keywords(profile_id)
    capability_body = _section(text, tuple(keywords["capabilities"]))
    capabilities = _capabilities(capability_body)
    if not capabilities:
        add_synth("capabilities[0]")
        capabilities = [{"trigger": "unknown", "inputs": [], "outputs": [], "constraints": []}]
    else:
        mapped.append({"source_path": "capabilities_section", "target_path": "capabilities", "value_sha256": sha256_text(capability_body.strip())})

    instruction_body = _section(text, tuple(keywords["instructions"]))
    instructions = _instructions(text, instruction_body)
    if not instructions:
        add_synth("instructions[0]")
        instructions = [{"step": 1, "text": "unknown"}]
    else:
        mapped.append({"source_path": "numbered_list", "target_path": "instructions", "value_sha256": sha256_text(str(len(instructions)))})

    front = _frontmatter(text) or {}
    for key in front:
        if key not in KNOWN_MANIFEST:
            dropped.append({"source_path": f"frontmatter.{key}", "reason_code": "unmapped_field", "loses_capability": "capab" in key.lower()})

    patterns = [re.compile(pattern, re.I) for pattern in load_schema().get("forbidden_value_patterns", [])]
    safe_instructions = []
    for item in instructions:
        value = item["text"]
        if any(pattern.search(value) for pattern in patterns):
            dropped.append({"source_path": "instructions", "reason_code": "limit_value", "loses_capability": True})
            value = "unknown"
        safe_instructions.append({"step": item["step"], "text": value})

    doc = {
        "schema_version": 1,
        "identity": {"name": name, "id": f"import-{import_id}", "version": version, "tags": []},
        "intent": {"summary": summary, "source_kind": "markdown"},
        "capabilities": capabilities,
        "instructions": safe_instructions,
        "examples": [],
        "resources": [],
        "provenance": {
            "source": source,
            "native_targets": ["unknown"],
            "import_id": import_id,
            "mapping_report_ref": report_id,
        },
    }
    report = {
        "report_id": report_id,
        "import_id": import_id,
        "source_sha256": sha256_text(text),
        "profile_id": profile_id,
        "format_recognized": bool(recognized),
        "mapped": mapped,
        "dropped": dropped,
        "synthesized": synthesized,
        "summary": {"mapped": len(mapped), "dropped": len(dropped), "synthesized": len(synthesized)},
    }
    return doc, report