from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

WARN_UNSUPPORTED = "UNSUPPORTED_SYNTAX"
WARN_DUP_KEY = "DUP_KEY"
WARN_SYNTAX = "YAML_SYNTAX"


@dataclass
class YamlResult:
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    ok: bool = True


def _warn(code: str, message: str, fix: str = "") -> Dict[str, str]:
    return {"code": code, "level": "warn", "message": message, "fix": fix}


def _indent(line: str) -> int:
    total = 0
    for char in line:
        if char == " ":
            total += 1
        elif char == "\t":
            total += 2
        else:
            break
    return total


def _blank(line: str) -> bool:
    return not line.strip()


def _comment_only(line: str) -> bool:
    return line.lstrip().startswith("#")


def _strip_comment(text: str) -> str:
    quote = ""
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "#" and (index == 0 or text[index - 1].isspace()):
            return text[:index].rstrip()
    return text.rstrip()


def _next_meaningful(lines: List[str], start: int) -> int:
    index = start
    while index < len(lines) and (_blank(lines[index]) or _comment_only(lines[index])):
        index += 1
    return index


def _split_key(text: str) -> Tuple[Optional[str], str]:
    quote = ""
    depth = 0
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char in "[{":
            depth += 1
            continue
        if char in "]}":
            depth = max(0, depth - 1)
            continue
        if char == ":" and depth == 0:
            rest = text[index + 1:]
            if rest == "" or rest[0].isspace():
                return text[:index].strip(), rest.strip()
    return None, text


def _unquote(text: str) -> str:
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return _decode_double(value[1:-1])
    return value


def _decode_double(text: str) -> str:
    result = []
    index = 0
    escape = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", '"': '"', "\\": "\\", "/": "/"}
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            if nxt == "u" and index + 5 < len(text):
                try:
                    result.append(chr(int(text[index + 2:index + 6], 16)))
                    index += 6
                    continue
                except ValueError:
                    pass
            result.append(escape.get(nxt, nxt))
            index += 2
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _decode_scalar(text: str, line_no: int, warnings: List[Dict[str, str]]) -> Any:
    value = text.strip()
    if not value:
        return ""
    if value[0] in "&*":
        warnings.append(_warn(WARN_UNSUPPORTED, f"第 {line_no} 行使用锚点或别名，已按字符串保留", "移除 & / * 语法"))
        return value
    if value.startswith("{"):
        warnings.append(_warn(WARN_UNSUPPORTED, f"第 {line_no} 行使用 flow map，已按字符串保留", "改用缩进映射"))
        return value
    if value.startswith("["):
        parsed = _parse_flow_list(value, line_no, warnings)
        return parsed if parsed is not None else value
    if value[0] in ("'", '"'):
        return _unquote(value)
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False
    if value in ("null", "Null", "NULL", "~"):
        return None
    return value


def _parse_flow_list(text: str, line_no: int, warnings: List[Dict[str, str]]) -> Optional[List[Any]]:
    if not text.endswith("]"):
        warnings.append(_warn(WARN_UNSUPPORTED, f"第 {line_no} 行 flow 列表未闭合，已按字符串保留", "改用块列表"))
        return None
    inner = text[1:-1].strip()
    if not inner:
        return []
    items = []
    buffer = []
    quote = ""
    depth = 0
    for char in inner:
        if quote:
            buffer.append(char)
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            buffer.append(char)
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            items.append(_decode_scalar("".join(buffer), line_no, warnings))
            buffer = []
            continue
        buffer.append(char)
    if buffer:
        items.append(_decode_scalar("".join(buffer), line_no, warnings))
    return items


def _is_block_indicator(text: str) -> bool:
    value = text.strip()
    return bool(value) and value[0] in "|>" and all(c in "|>+-0123456789 " for c in value)


def _fold(lines: List[str]) -> str:
    out: List[str] = []
    for line in lines:
        if line == "":
            out.append("\n")
            continue
        if out and out[-1] not in ("\n", " ") and not out[-1].endswith("\n"):
            out.append(" ")
        out.append(line)
    return "".join(out)


def _parse_block_scalar(lines: List[str], start: int, parent_indent: int, indicator: str) -> Tuple[str, int]:
    style = indicator[0]
    chomp = "-" if "-" in indicator else "+" if "+" in indicator else ""
    collected: List[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if _blank(line):
            collected.append("")
            index += 1
            continue
        if _indent(line) <= parent_indent:
            break
        collected.append(line)
        index += 1
    nonempty = [_indent(line) for line in collected if line.strip()]
    base = min(nonempty) if nonempty else 0
    dedented = [line[base:] if len(line) >= base else "" for line in collected]
    if style == "|":
        value = "\n".join(dedented)
    else:
        value = _fold(dedented)
    if chomp == "-":
        return value.rstrip("\n"), index
    if chomp == "+":
        return value + ("\n" if collected else ""), index
    return value.rstrip("\n") + "\n" if value.strip() else "", index


def _parse_inline_map_item(
    content: str, lines: List[str], index: int, item_indent: int, line_no: int, warnings: List[Dict[str, str]]
) -> Tuple[Dict[str, Any], int]:
    key, rest = _split_key(content)
    result: Dict[str, Any] = {}
    if key is None:
        warnings.append(_warn(WARN_SYNTAX, f"第 {line_no} 行列表项无法解析为映射", "检查 key: value 格式"))
        return result, index
    name = _unquote(key)
    if _is_block_indicator(rest):
        result[name], index = _parse_block_scalar(lines, index, item_indent, rest)
    elif rest:
        result[name] = _decode_scalar(rest, line_no, warnings)
    else:
        nxt = _next_meaningful(lines, index)
        if nxt < len(lines) and _indent(lines[nxt]) > item_indent:
            result[name], index = _parse_block(lines, nxt, _indent(lines[nxt]), warnings, 0)
        else:
            result[name] = ""
    nxt = _next_meaningful(lines, index)
    if nxt < len(lines) and _indent(lines[nxt]) > item_indent:
        sub, index = _parse_map(lines, nxt, _indent(lines[nxt]), warnings, 0)
        result.update(sub)
    return result, index


def _parse_list(
    lines: List[str], start: int, indent: int, warnings: List[Dict[str, str]], depth: int
) -> Tuple[List[Any], int]:
    result: List[Any] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if _blank(line):
            index += 1
            continue
        if _comment_only(line):
            index += 1
            continue
        ind = _indent(line)
        if ind < indent:
            break
        if ind > indent:
            warnings.append(_warn(WARN_SYNTAX, f"第 {index + 1} 行缩进异常，已跳过", "对齐列表项缩进"))
            index += 1
            continue
        content = _strip_comment(line[ind:]).strip()
        if not content.startswith("-") or (len(content) > 1 and content[1] not in " \t"):
            break
        payload = content[1:].strip()
        index += 1
        if not payload:
            nxt = _next_meaningful(lines, index)
            if nxt < len(lines) and _indent(lines[nxt]) > indent:
                value, index = _parse_block(lines, nxt, _indent(lines[nxt]), warnings, depth + 1)
                result.append(value)
            else:
                result.append(None)
            continue
        if _looks_like_map(payload):
            item, index = _parse_inline_map_item(payload, lines, index, indent, index, warnings)
            result.append(item)
        elif payload.startswith("- "):
            value, index = _parse_list(lines, index - 1, ind + 2, warnings, depth + 1)
            result.append(value)
        else:
            result.append(_decode_scalar(payload, index, warnings))
    return result, index


def _looks_like_map(text: str) -> bool:
    if text.startswith(("'", '"', "[", "{")):
        return False
    key, rest = _split_key(text)
    return key is not None


def _parse_map(
    lines: List[str], start: int, indent: int, warnings: List[Dict[str, str]], depth: int
) -> Tuple[Dict[str, Any], int]:
    result: Dict[str, Any] = {}
    index = start
    while index < len(lines):
        line = lines[index]
        if _blank(line):
            index += 1
            continue
        if _comment_only(line):
            index += 1
            continue
        ind = _indent(line)
        if ind < indent:
            break
        if ind > indent:
            warnings.append(_warn(WARN_SYNTAX, f"第 {index + 1} 行缩进异常，已跳过", "对齐映射键缩进"))
            index += 1
            continue
        content = _strip_comment(line[ind:]).strip()
        if content in ("---", "..."):
            warnings.append(_warn(WARN_UNSUPPORTED, f"第 {index + 1} 行出现多文档分隔符，已忽略", "frontmatter 只保留一个文档"))
            index += 1
            continue
        key, rest = _split_key(content)
        if key is None:
            warnings.append(_warn(WARN_SYNTAX, f"第 {index + 1} 行缺少键值分隔符", "使用 key: value 格式"))
            index += 1
            continue
        name = _unquote(key)
        if not name:
            warnings.append(_warn(WARN_SYNTAX, f"第 {index + 1} 行键为空", "填写键名"))
            index += 1
            continue
        if name in result:
            warnings.append(_warn(WARN_DUP_KEY, f"重复键 {name}，已保留最后值", f"删除第 {index + 1} 行之前的重复 {name}"))
        index += 1
        if _is_block_indicator(rest):
            result[name], index = _parse_block_scalar(lines, index, indent, rest)
        elif rest:
            result[name] = _decode_scalar(rest, index, warnings)
        else:
            nxt = _next_meaningful(lines, index)
            if nxt < len(lines) and _indent(lines[nxt]) > indent:
                result[name], index = _parse_block(lines, nxt, _indent(lines[nxt]), warnings, depth + 1)
            else:
                result[name] = ""
    return result, index


def _parse_block(
    lines: List[str], start: int, indent: int, warnings: List[Dict[str, str]], depth: int
) -> Tuple[Any, int]:
    if depth > 40:
        warnings.append(_warn(WARN_SYNTAX, "嵌套层级过深，已停止解析", "减少嵌套"))
        return {}, len(lines)
    index = _next_meaningful(lines, start)
    if index >= len(lines):
        return {}, index
    first = _strip_comment(lines[index][_indent(lines[index]):]).strip()
    if first.startswith("-") and (len(first) == 1 or first[1] in " \t"):
        return _parse_list(lines, index, _indent(lines[index]), warnings, depth)
    return _parse_map(lines, index, _indent(lines[index]), warnings, depth)


def parse_yaml(text: str) -> YamlResult:
    warnings: List[Dict[str, str]] = []
    normalized = (text or "").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if "\t" in normalized:
        warnings.append(_warn(WARN_SYNTAX, "YAML 中存在制表符缩进，已按两个空格处理", "改用空格缩进"))
    if not normalized.strip():
        return YamlResult({}, warnings, True)
    try:
        data, _index = _parse_block(normalized.split("\n"), 0, 0, warnings, 0)
    except Exception as exc:  # noqa: BLE001
        return YamlResult({}, warnings + [_warn(WARN_SYNTAX, f"YAML 解析失败：{exc}", "检查缩进、引号与冒号")], False)
    if not isinstance(data, dict):
        return YamlResult({}, warnings + [_warn(WARN_SYNTAX, "frontmatter 顶层不是映射", "使用 key: value 结构")], False)
    return YamlResult(data, warnings, True)


def dump_yaml(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    for key in sorted(data.keys()):
        value = data[key]
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key in sorted(value.keys()):
                lines.append(f"  {sub_key}: {_dump_scalar(value[sub_key])}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_dump_scalar(item)}")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    return "\n".join(lines) + "\n"


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if any(char in text for char in ":#\n'\"") or text.strip() != text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return text