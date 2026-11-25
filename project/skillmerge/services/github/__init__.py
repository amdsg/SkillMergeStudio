"""GitHub 只读集成：搜索、推荐（trending）、下载。"""
from .client import GithubClient
from .search import search, trending
from .download import download

__all__ = ["GithubClient", "search", "trending", "download"]
