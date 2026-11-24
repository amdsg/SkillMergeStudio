#!/usr/bin/env python3
"""Skill Workbench local agent entry point."""
from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

WB_ROOT = Path(__file__).resolve().parent.parent
if str(WB_ROOT) not in sys.path:
    sys.path.insert(0, str(WB_ROOT))

from agent.api.applicability import ack_endpoint, resolve_endpoint
from agent.api.convert_endpoint import convert_endpoint
from agent.api.diagnostics import get_diagnostics
from agent.api.download import download
from agent.api.health import health
from agent.api.import_endpoint import import_endpoint
from agent.api.install import preview_endpoint
from agent.api.install_apply import apply_endpoint
from agent.api.merge import preview_endpoint as merge_preview
from agent.api.pair import confirm_code, create_code, pair_status
from agent.api.records import list_records
from agent.api.search import search_endpoint
from agent.api.targets import list_targets, target_tools
from agent.api.upgrade import check_endpoint
from agent.core.paths import ensure_store
from agent.http.router import Router
from agent.http.server import WorkbenchServer


def build_router() -> Router:
    router = Router()
    router.add("GET", "/health", health)
    router.add("GET", "/targets", list_targets)
    router.add("GET", "/targets/{id}/tools", target_tools)
    router.add("POST", "/applicability/resolve", resolve_endpoint)
    router.add("POST", "/applicability/ack", ack_endpoint)
    router.add("POST", "/search", search_endpoint)
    router.add("POST", "/download", download)
    router.add("POST", "/install/preview", preview_endpoint)
    router.add("POST", "/install/apply", apply_endpoint)
    router.add("POST", "/pair/create", create_code)
    router.add("POST", "/pair/confirm", confirm_code)
    router.add("GET", "/pair/status", pair_status)
    router.add("POST", "/convert", convert_endpoint)
    router.add("POST", "/import", import_endpoint)
    router.add("POST", "/merge", merge_preview)
    router.add("POST", "/upgrade/check", check_endpoint)
    router.add("GET", "/records/{name}", list_records)
    router.add("GET", "/diagnostics/{id}", get_diagnostics)
    return router


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Skill Workbench local agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    ensure_store()
    runtime_path = WB_ROOT / "agent" / "store" / "runtime.json"
    if args.self_check:
        server = WorkbenchServer(build_router(), host=args.host, port=0, runtime_path=runtime_path)
        info = server.start()
        server.stop()
        print(json.dumps({"ok": True, "data": {"port": info["port"], "self_check": "passed"}}, ensure_ascii=False))
        return 0
    server = WorkbenchServer(build_router(), host=args.host, port=args.port, runtime_path=runtime_path)
    info = server.start()
    print(json.dumps({"ok": True, "data": info}, ensure_ascii=False))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())