from __future__ import annotations

import argparse
import sys

from skillmerge.app import build_app, run_server
from skillmerge.util.errors import DomainError


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="server.py", description="Skill Merge Studio 本地服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（固定本机回环）")
    parser.add_argument("--port", type=int, default=8765, help="首选端口，默认 8765")
    parser.add_argument("--data-dir", default="", help="数据目录，默认 ./data")
    parser.add_argument("--force", action="store_true", help="忽略已存在实例检测")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("只允许绑定 127.0.0.1", file=sys.stderr)
        return 2
    try:
        server = build_app(
            host=args.host,
            preferred_port=args.port,
            data_dir=args.data_dir or None,
            check_pid=not args.force,
        )
    except DomainError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    if server is None:
        return 0
    return run_server(server, args.host)


if __name__ == "__main__":
    raise SystemExit(main())