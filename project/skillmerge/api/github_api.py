"""GitHub 搜索 / 推荐 / 下载 / 更新检测 HTTP 端点。"""
from __future__ import annotations

from ..services.github.search import search as search_service
from ..services.github.search import trending as trending_service
from ..services.github.download import download as download_service
from ..services.github.upgrade import check_update as check_update_service


def _payload(request) -> dict:
    data = request.json_data or {}
    return data if isinstance(data, dict) else {}


def search(ctx, request):
    return 200, search_service(ctx.github_client, _payload(request))


def trending(ctx, request):
    return 200, trending_service(ctx.github_client, _payload(request))


def download(ctx, request):
    return 200, download_service(ctx.github_client, _payload(request))


def check_update(ctx, request):
    return 200, check_update_service(ctx.github_client, _payload(request))


def health(ctx, request):
    return 200, ctx.github_client.health()
