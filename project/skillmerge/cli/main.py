from __future__ import annotations

import argparse
import sys

from .commands import (
    run_classify,
    run_export,
    run_merge,
    run_platforms,
    run_scan,
    run_serve,
    run_validate,
)
from .output import emit_error
from ..util.errors import DomainError


class Parser(argparse.ArgumentParser):
    def error(self, message):
        emit_error("INVALID_ARGUMENT", message, "查看 skillmerge --help")
        self.print_usage(sys.stderr)
        raise SystemExit(2)


def _data_dir(parser):
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--json", action="store_true", help="输出 JSON（默认即为 JSON）")


def build_parser() -> Parser:
    parser = Parser(prog="skillmerge", description="Skill Merge Studio CLI")
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="扫描技能目录")
    scan.add_argument("--root", action="append", default=[], help="扫描根目录，可重复")
    scan.add_argument("--depth", type=int, default=0)
    scan.add_argument("--limit", type=int, default=0)
    scan.add_argument("--time-limit", type=int, default=0)
    scan.add_argument("--refresh", action="store_true")
    _data_dir(scan)
    serve = sub.add_parser("serve", help="启动本地 Web 服务")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--data-dir", default="")
    serve.add_argument("--force", action="store_true")
    platforms = sub.add_parser("platforms", help="列出平台治理清单")
    platforms.add_argument("--kind", default="")
    platforms.add_argument("--group", default="")
    platforms.add_argument("--verified", dest="verified", action="store_true", default=None)
    platforms.add_argument("--no-verified", dest="verified", action="store_false")
    platforms.add_argument("--evidence", default="")
    platforms.add_argument("--q", default="")
    platforms.add_argument("--sort", default="status")
    platforms.add_argument("--limit", type=int, default=0)
    platforms.add_argument("--offset", type=int, default=0)
    _data_dir(platforms)
    classify = sub.add_parser("classify", help="对已扫描技能重新分类")
    classify.add_argument("--skill-ids", default="", help="逗号分隔的技能 id，省略表示全部")
    classify.add_argument("--use-ai", action="store_true")
    classify.add_argument("--confirm-ai", action="store_true")
    _data_dir(classify)
    merge = sub.add_parser("merge", help="合并技能并产出产物")
    merge.add_argument("--sources", required=True, help="逗号分隔的技能 id")
    merge.add_argument("--name", required=True)
    merge.add_argument("--platform", default="generic")
    merge.add_argument("--strategy", default="keep-all")
    merge.add_argument("--out", default="", help="产物输出目录（需在 save_dir 内）")
    merge.add_argument("--use-ai", action="store_true")
    merge.add_argument("--confirm-ai", action="store_true")
    _data_dir(merge)
    export = sub.add_parser("export", help="把产物导出到目标平台")
    export.add_argument("--artifact", required=True)
    export.add_argument("--platform", required=True)
    export.add_argument("--mode", default="zip", choices=("dir", "zip", "install", "download"))
    export.add_argument("--length-mode", default="full", choices=("full", "compact", "minimal"))
    export.add_argument("--profile", default="generic")
    export.add_argument("--name-en", default="")
    export.add_argument("--install-scope", default="global", choices=("global", "project"))
    export.add_argument("--confirm-candidate", action="store_true")
    _data_dir(export)
    validate = sub.add_parser("validate", help="按平台规则校验产物目录")
    validate.add_argument("--artifact", required=True)
    validate.add_argument("--platform", required=True)
    validate.add_argument("--name-en", default="")
    _data_dir(validate)
    return parser


HANDLERS = {
    "scan": run_scan,
    "serve": run_serve,
    "platforms": run_platforms,
    "classify": run_classify,
    "merge": run_merge,
    "export": run_export,
    "validate": run_validate,
}


def main(argv=None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        args_list = ["serve"]
    parser = build_parser()
    args = parser.parse_args(args_list)
    handler = HANDLERS.get(getattr(args, "command", ""))
    if handler is None:
        parser.error("请指定子命令：scan、classify、merge、export、validate、platforms 或 serve")
        return 2
    try:
        return handler(args)
    except DomainError as exc:
        emit_error(exc.code, exc.message, exc.fix)
        return 2 if exc.status == 400 else 1
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001
        emit_error("INTERNAL_ERROR", str(exc), "查看 stderr 日志后重试")
        return 1