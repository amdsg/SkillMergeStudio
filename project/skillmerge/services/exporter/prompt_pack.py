from __future__ import annotations

import math
import re
import textwrap
from typing import Any, Dict, List, Tuple

from ..parser.frontmatter import read_document
from ..parser.markdown import parse_markdown

SECTIONS = ("role", "scenario", "triggers", "workflow", "tools", "constraints", "examples", "checklist")
TITLES = {
    "role": "角色", "scenario": "适用场景", "triggers": "触发条件",
    "workflow": "工作流", "tools": "工具与输入输出约定", "constraints": "约束与禁止事项",
    "examples": "示例", "checklist": "自检清单",
}
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SELF_PATTERNS = ("./", "../", "C:\\", "/Users/", "assets/", "见文件", "~~/")
PROFILES = ("claude", "gpt", "gemini", "qwen", "kimi", "doubao", "deepseek", "generic")


def _sections(body: str) -> Dict[str, str]:
    headings = parse_markdown(body).headings
    lines = body.split("\n")
    result = {}
    for index, item in enumerate(headings):
        start = int(item["line"])
        end = len(lines)
        for later in headings[index + 1:]:
            if int(later["level"]) <= int(item["level"]):
                end = int(later["line"]) - 1
                break
        result[str(item["norm"])] = "\n".join(lines[start:end]).strip("\n")
    return result


def _find(sections: Dict[str, str], words: Tuple[str, ...]) -> str:
    for key, value in sections.items():
        if any(word in key for word in words):
            return value
    return ""


def _clean(text: str) -> str:
    return "\n".join(line for line in str(text or "").split("\n") if not line.strip().startswith("<!--")).strip()


def _sentences(text: str, limit: int = 2) -> str:
    parts = re.split(r"(?<=[。！？.!?])\s*", _clean(text))
    return " ".join(part.strip() for part in parts[:limit] if part.strip())


def _steps(text: str) -> List[str]:
    steps = []
    for line in _clean(text).split("\n"):
        value = re.sub(r"^\s*(?:[-*+]|\d+[.)、])\s*", "", line).strip()
        if value:
            steps.append(value)
    return steps


def _bullet(text: str, limit: int = 5) -> List[str]:
    return [f"- {step}" for step in _steps(text)[:limit]]


def _default_workflow(name: str) -> str:
    return f"1. 理解任务目标与输入。\n2. 按 {name} 的规则执行。\n3. 输出结果并自检。"


def _build_sections(document, name: str, description: str, sources: List[Dict[str, Any]]) -> Dict[str, str]:
    raw = _sections(document.body)
    workflow = _find(raw, ("工作流", "工作流程", "流程", "workflow"))
    tools = _find(raw, ("工具", "输入输出", "环境要求", "tools"))
    constraints = _find(raw, ("约束", "禁止", "注意事项", "constraint"))
    examples = _find(raw, ("示例", "例子", "example"))
    checklist = _find(raw, ("自检", "检查清单", "checklist"))
    triggers = _find(raw, ("触发", "trigger"))
    scenario_names = "、".join(str(item.get("name", "")) for item in sources[:3])
    return {
        "role": f"你是一名 {name} 助手，负责按照给定流程可靠完成相关任务。",
        "scenario": f"{description} 适用于 {scenario_names or '多个来源技能'} 覆盖的工作场景。",
        "triggers": triggers.strip() or f"当用户提出与 {name} 相关的任务，或需要执行其工作流时。",
        "workflow": workflow.strip() or _default_workflow(name),
        "tools": tools.strip() or "输入：用户提供的文本、文件或数据。输出：结构化结果与必要说明。",
        "constraints": constraints.strip() or "- 不得编造事实。\n- 不得删除输入中的关键信息。\n- 不确定时明确说明并请求补充。",
        "examples": examples.strip() or "（未提供示例，可按实际任务补充。）",
        "checklist": checklist.strip() or "- 目标是否明确\n- 输入是否完整\n- 流程是否执行\n- 结果是否自检\n- 风险是否说明",
    }


def _compact(sections: Dict[str, str]) -> Dict[str, str]:
    result = dict(sections)
    role = _sentences(sections["role"], 1).split("，")[0].strip()
    result["role"] = (role or "执行技能工作流") + "。"
    result["scenario"] = _sentences(sections["scenario"], 1)[:40]
    result["triggers"] = _sentences(sections["triggers"], 1)[:40]
    steps = _steps(sections["workflow"])
    result["workflow"] = "\n".join(f"{index}. {_sentences(step, 1)}" for index, step in enumerate(steps, start=1))
    result["tools"] = "输入见任务描述；输出结构化结果与必要说明。"
    result["constraints"] = "\n".join(_bullet(sections["constraints"], 3)) or _sentences(sections["constraints"], 2)
    result["examples"] = "（示例略，详见 full 档。）"
    result["checklist"] = "\n".join(_bullet(sections["checklist"], 3))
    return result


def _minimal(sections: Dict[str, str]) -> Dict[str, str]:
    steps = _steps(sections["workflow"])[:5]
    workflow = "\n".join(f"{index}. {_sentences(step, 1)}" for index, step in enumerate(steps, start=1))
    role = _sentences(sections["role"], 1).split("，")[0].strip()
    return {
        "role": (role or "执行技能工作流") + "。",
        "workflow": workflow,
        "constraints": "\n".join(_bullet(sections["constraints"], 5)),
    }


def _wrap_lines(text: str, width: int = 40) -> str:
    lines = []
    for line in text.split("\n"):
        if line.startswith(("#", "-", "<", "【")) or len(line) <= width:
            lines.append(line)
        else:
            lines.extend(textwrap.wrap(line, width=width) or [line])
    return "\n".join(lines)


def _render(profile: str, sections: Dict[str, str], minimal: bool = False, compact: bool = False) -> str:
    order = [key for key in SECTIONS if key in sections]
    if profile == "claude":
        blocks = []
        for key in order:
            if key == "workflow":
                steps = _steps(sections[key])
                body = "\n".join(f'<step n="{index}">{step}</step>' for index, step in enumerate(steps, start=1))
                blocks.append(f"<workflow>\n{body}\n</workflow>")
            else:
                blocks.append(f"<{key}>\n{sections[key]}\n</{key}>")
        return "\n\n".join(blocks) + "\n"
    if profile == "generic":
        return "\n\n".join(f"【{TITLES[key]}】\n{sections[key]}" for key in order) + "\n"
    lines = []
    if minimal:
        lines.append("（本档位仅含工作流与约束）")
        lines.append("")
    for key in order:
        lines.append(f"## {TITLES[key]}")
        content = sections[key]
        if key == "workflow" and not content.lstrip().startswith(tuple("0123456789-")):
            steps = _steps(content)
            content = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        if profile in ("qwen", "kimi", "doubao", "deepseek"):
            content = _wrap_lines(content)
        if compact:
            lines.append(content)
        else:
            lines.extend(["", content, ""])
    return "\n".join(lines).rstrip() + "\n"


def token_estimate(text: str) -> int:
    cjk = len(CJK.findall(text))
    other = len(text) - cjk
    return int(math.ceil(cjk / 1.5 + other / 4))


def self_contained_warnings(text: str) -> List[Dict[str, str]]:
    hits = [pattern for pattern in SELF_PATTERNS if pattern in text]
    if not hits:
        return []
    return [
        {
            "code": "PROMPT_NOT_SELF_CONTAINED",
            "level": "warn",
            "message": f"提示词引用了外部路径：{', '.join(hits)}",
            "fix": "将资源说明改为内联描述，或把必要内容直接写入提示词",
        }
    ]


def generate(
    artifact,
    rule: Dict[str, Any],
    name: str,
    description: str,
    sources: List[Dict[str, Any]],
    length_mode: str = "full",
    profile: str = "generic",
) -> Dict[str, Any]:
    path = artifact.dir_path + "/SKILL.md"
    document = read_document(path)
    sections = _build_sections(document, name, description, sources)
    full = _render(profile if profile in PROFILES else "generic", sections)
    if length_mode == "compact":
        compact = _compact(sections)
        text = _render(profile if profile in PROFILES else "generic", compact, compact=True)
        if len(text) > 0.70 * len(full):
            compact["examples"] = ""
            compact["scenario"] = compact["scenario"][:15]
            compact["triggers"] = compact["triggers"][:15]
            compact["checklist"] = "\n".join(_bullet(sections["checklist"], 2))
            text = _render(profile if profile in PROFILES else "generic", compact, compact=True)
        warnings = [] if len(text) <= 0.70 * len(full) else [
            {"code": "LENGTH_MODE_EXCEEDED", "level": "warn", "message": "compact 档仍偏大", "fix": "建议拆分技能"}
        ]
    elif length_mode == "minimal":
        minimal_sections = _minimal(sections)
        text = _render(profile if profile in PROFILES else "generic", minimal_sections, minimal=True)
        warnings = []
    else:
        text = full
        warnings = []
    warnings.extend(self_contained_warnings(text))
    tags = sorted({str(item.get("category", "")) for item in sources if item.get("category")} - {""})
    manifest = {
        "name": name,
        "description": description,
        "tags": tags,
        "sources": [{"skill_id": item.get("skill_id", ""), "name": item.get("name", ""), "path": item.get("path", "")} for item in sources],
        "token_estimate": token_estimate(text),
        "estimate": True,
        "estimator": "cjk/1.5+other/4",
        "length_mode": length_mode,
        "profile": profile,
        "files": ["prompt.md", "manifest.json", "README.txt"],
    }
    readme = (
        f"{name}\n{'=' * len(name)}\n\n"
        f"用途：{description}\n\n"
        f"篇幅：{length_mode}；风格：{profile}\n\n"
        f"文件：prompt.md（可直接粘贴到聊天模型）、manifest.json、README.txt\n"
    )
    return {"text": text, "readme": readme, "manifest": manifest, "warnings": warnings}