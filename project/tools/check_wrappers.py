from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "start.bat": "python server.py",
    "start.command": "python3 server.py",
    "start.sh": "python3 server.py",
}


def main() -> int:
    issues = []
    for name, marker in EXPECTED.items():
        path = ROOT / name
        if not path.is_file():
            issues.append(f"缺少包装脚本：{name}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            issues.append(f"{name} 未转调 {marker}")
        lowered = text.lower()
        if "if " in lowered or "case " in lowered:
            issues.append(f"{name} 含平台分支")
        if "--port" in text:
            issues.append(f"{name} 硬编码端口参数")
    if issues:
        print("包装脚本门禁失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    print("包装脚本门禁通过（三平台脚本仅转调启动器）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())