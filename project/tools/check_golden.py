from __future__ import annotations

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "golden")
CHANGELOG = os.path.join(ROOT, "CHANGELOG-golden.md")


def main() -> int:
    issues = []
    if not os.path.isfile(CHANGELOG):
        issues.append("缺少 CHANGELOG-golden.md")
    changelog = open(CHANGELOG, "r", encoding="utf-8").read() if os.path.isfile(CHANGELOG) else ""
    for name in sorted(os.listdir(GOLDEN)) if os.path.isdir(GOLDEN) else []:
        expected = os.path.join(GOLDEN, name, "expected")
        sums = os.path.join(expected, "SHA256SUMS")
        if not os.path.isfile(sums):
            issues.append(f"{name}: 缺少 SHA256SUMS")
            continue
        if name not in changelog:
            issues.append(f"{name}: CHANGELOG-golden.md 无记录")
        listed = set()
        for line in open(sums, "r", encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            digest, rel = line.split("  ", 1)
            listed.add(rel)
            path = os.path.join(expected, rel)
            if not os.path.isfile(path):
                issues.append(f"{name}: 缺失文件 {rel}")
                continue
            actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            if actual != digest:
                issues.append(f"{name}: {rel} 哈希不匹配")
        actual_files = set()
        for dirpath, dirnames, filenames in os.walk(expected):
            dirnames.sort()
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), expected).replace(os.sep, "/")
                if rel != "SHA256SUMS":
                    actual_files.add(rel)
        if actual_files != listed:
            issues.append(f"{name}: 文件集合与 SHA256SUMS 不一致")
    if issues:
        print("golden 检查失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    print("golden 检查通过", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())