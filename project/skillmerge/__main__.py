from __future__ import annotations

import sys


def main(argv=None) -> int:
    from .cli.main import main as cli_main

    args = list(sys.argv[1:] if argv is None else argv)
    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())