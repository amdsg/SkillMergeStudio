"""Record listing endpoint."""
from __future__ import annotations

from agent.core.records import read_all


def list_records(params, body, request_id):
    name = str(params.get("name", ""))
    if name not in ("downloads", "conversions", "merges", "installs", "upgrades"):
        return {"name": name, "items": [], "error_code": "E_BAD_REQUEST"}
    return {"name": name, "items": read_all(name)}