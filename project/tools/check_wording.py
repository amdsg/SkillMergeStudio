from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERNS = [
    re.compile(r"支持\s*(27|28|100|99)\s*个\s*(Skill\s*)?平台", re.I),
    re.compile(r"(27|28|100|99)\s*个\s*(Skill\s*)?平台", re.I),
    re.compile(r"(27|28|100|99)\s*(Skill\s*)?平台注册表", re.I),
    re.compile(r"(?:361|338|321)\s*条[^\n。]{0,12}(?:全部|均|逐条)?[^\n。]{0,6}(?:通过|已验证)"),
    re.compile(r"已继承\s*189\s*条"),
    re.compile(r"支持\s*25\s*个\s*(?:平台|模型|目标)"),
    re.compile(r"证据\s*[=＝]\s*支持"),
    re.compile(r"verified\s*\+\s*evidence", re.I),
]
TARGETS = ("README.txt", "web/index.html", "web/js")
NEGATION = re.compile(r"不得|禁止|未|不|无法|不可|没有|cannot|not", re.I)


def _files() -> list:
    result = []
    for target in TARGETS:
        path = os.path.join(ROOT, target)
        if os.path.isfile(path):
            result.append(path)
        elif os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = sorted(name for name in dirnames if name != "node_modules")
                for name in sorted(filenames):
                    if name.endswith((".js", ".html", ".css", ".txt")):
                        result.append(os.path.join(dirpath, name))
    return result


def main() -> int:
    issues = []
    for path in _files():
        text = open(path, "r", encoding="utf-8", errors="replace").read()
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                window = text[max(0, match.start() - 14): match.end() + 14]
                if NEGATION.search(window):
                    continue
                issues.append(f"{os.path.relpath(path, ROOT)}:{line}: {match.group(0)}")
    if issues:
        print("文案门禁失败：", file=sys.stderr)
        for item in issues:
            print(" - " + item, file=sys.stderr)
        return 1
    print(f"文案门禁通过（{len(_files())} 个文件）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())