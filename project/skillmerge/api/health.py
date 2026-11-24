from __future__ import annotations

import time

from .. import __version__


def health(ctx, request):
    stats = ctx.jobs.stats()
    return 200, {
        "ok": True,
        "version": __version__,
        "uptime_s": int(time.monotonic() - ctx.started_at),
        "jobs": stats,
        "db": "ok",
        "port": ctx.port,
    }