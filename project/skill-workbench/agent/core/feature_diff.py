"""Feature-level three-way difference classification with an acknowledgement gate."""
from __future__ import annotations

from agent.core.hashing import sha256_text
from agent.http.errors import DomainError

SUPPORTED = "supported"
DEGRADED = "degraded"
UNSUPPORTED = "unsupported"


def classify(features: list[str], target_capabilities: list[str], degradations: dict | None = None) -> dict:
    capabilities = set(target_capabilities or [])
    degradation_map = degradations or {}
    items = []
    counts = {SUPPORTED: 0, DEGRADED: 0, UNSUPPORTED: 0}
    for feature in features:
        if feature in capabilities:
            status, plan = SUPPORTED, None
        elif feature in degradation_map:
            status, plan = DEGRADED, str(degradation_map[feature])
        else:
            status, plan = UNSUPPORTED, None
        counts[status] += 1
        items.append({"feature": feature, "status": status, "degradation": plan})
    token = sha256_text("|".join(sorted(features)) + "|" + "|".join(sorted(capabilities)))[:16]
    return {
        "items": items,
        "counts": counts,
        "total": len(features),
        "requires_ack": counts[DEGRADED] > 0 or counts[UNSUPPORTED] > 0,
        "ack_token": token,
    }


def require_ack(result: dict, ack: str) -> None:
    if result.get("requires_ack") and str(ack or "") != result.get("ack_token"):
        raise DomainError("E_FEATURE_ACK_REQUIRED", "wb.error.feature_ack_required", status=409,
                          params={"ack_token": result.get("ack_token")}, fix_key="wb.fix.ack_features")