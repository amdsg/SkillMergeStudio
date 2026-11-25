"""GitHub 只读集成：搜索、推荐（trending）、下载、更新检测。"""
from .client import GithubClient
from .search import search, trending
from .download import download
from .upgrade import check_update

__all__ = ["GithubClient", "search", "trending", "download", "check_update"]
