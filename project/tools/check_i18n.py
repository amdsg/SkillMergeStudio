from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "web" / "js" / "i18n"
SCAN_FILES = [ROOT / "web" / "js" / "app.js"] + sorted((ROOT / "web" / "js" / "views").glob("*.js"))
CJK = re.compile(r"[\u4e00-\u9fff]")
ALLOW = (
    re.compile(r"^\s*//"),
    re.compile(r"^\s*\*"),
)


def keys(path: Path) -> set:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'^\s*"([^"]+)"\s*:', text, re.M))


def scan_hardcoded(path: Path) -> list:
    issues = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not CJK.search(line):
            continue
        if any(pattern.search(line) for pattern in ALLOW):
            continue
        issues.append(f"{path.relative_to(ROOT)}:{number}: 硬编码中文：{line.strip()[:100]}")
    return issues


def main() -> int:
    zh = keys(I18N / "zh.js")
    en = keys(I18N / "en.js")
    issues = []
    if zh != en:
        only_zh = sorted(zh - en)
        only_en = sorted(en - zh)
        if only_zh:
            issues.append(f"仅中文存在的键：{only_zh}")
        if only_en:
            issues.append(f"仅英文存在的键：{only_en}")
    for path in SCAN_FILES:
        issues.extend(scan_hardcoded(path))
    if issues:
        print("i18n 门禁失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    print(f"i18n 门禁通过（{len(zh)} 个键，中文/英文一致，视图无硬编码中文）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())