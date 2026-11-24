from __future__ import annotations

import pytest

from skillmerge.services.history.rebuild import RebuildService
from skillmerge.util.errors import DomainError


class _Registry:
    def require(self, platform):
        return {"name": {"max_length": 64, "forbidden_parts": ["claude", "anthropic"]}}


class _Artifact:
    platform = "claude"
    name = "demo"


def _service() -> RebuildService:
    return RebuildService(None, None, None, _Registry())


def test_forbidden_name_is_blocked():
    with pytest.raises(DomainError) as exc:
        _service()._preflight(_Artifact(), {"name": "claude-helper"})
    assert exc.value.code == "EXPORT_BLOCKED"
    assert "claude" in exc.value.fix


def test_valid_name_passes():
    _service()._preflight(_Artifact(), {"name": "helper-skill"})


def test_long_name_is_blocked():
    with pytest.raises(DomainError):
        _service()._preflight(_Artifact(), {"name": "a" * 70})


def test_without_registry_is_noop():
    RebuildService(None, None, None)._preflight(_Artifact(), {"name": "claude-helper"})