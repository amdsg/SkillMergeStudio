from __future__ import annotations

from typing import Any, Dict

from ..services.exporter.platform_registry.params import validate_platform_params


def platform_params(request, registry) -> Dict[str, Any]:
    return validate_platform_params(
        {
            "kind": request.q("kind", ""),
            "group": request.q("group", ""),
            "verified": request.q("verified", ""),
            "evidence": request.q("evidence", ""),
            "q": request.q("q", ""),
            "sort": request.q("sort", "status"),
            "limit": request.q("limit", ""),
            "offset": request.q("offset", ""),
        },
        registry,
    )