from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from skillmerge.services.exporter.platform_registry.discovery_reader import load_latest, load_round


def _report(result, source: str) -> Dict[str, Any]:
    if result is None:
        return {"ok": False, "source": source, "error": "探测记录不存在"}
    errors = [item for item in result.issues if item.get("severity") == "error"]
    return {
        "ok": not errors,
        "source": source,
        "round": result.round_name,
        "summary": result.summary,
        "issues": result.issues,
        "error_count": len(errors),
    }


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and not args[0].startswith("-"):
        path = os.path.abspath(args[0])
        result = load_round(path)
        source = path
    else:
        directory = os.path.join(ROOT, "platforms", "discovery")
        result = load_latest(directory)
        source = directory
    report = _report(result, source)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())