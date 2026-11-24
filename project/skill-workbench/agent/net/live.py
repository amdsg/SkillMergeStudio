"""Live-mode gate and shared GithubClient factory.

Real GitHub access is opt-in and read-only. The agent stays in fixture mode
unless ``WB_LIVE_GITHUB=1`` or ``WB_GITHUB_TOKEN`` is set in the environment,
so tests and offline runs never touch the network.
"""
from __future__ import annotations

import os

from agent.net.github_client import GithubClient

_client: GithubClient | None = None


def is_live() -> bool:
    return os.environ.get("WB_LIVE_GITHUB", "") == "1" or bool(os.environ.get("WB_GITHUB_TOKEN", ""))


def get_client() -> GithubClient:
    global _client
    if _client is None:
        _client = GithubClient(token=os.environ.get("WB_GITHUB_TOKEN", ""))
    return _client
