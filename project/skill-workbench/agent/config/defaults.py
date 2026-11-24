"""Capability defaults. Every high-risk capability is disabled by default."""

CAPABILITIES = {
    "real_write": False,
    "upgrade_replace": False,
    "official_claim": False,
    "binary_convert": False,
    "auto_check": False,
}

CAPABILITY_IDS = tuple(CAPABILITIES)
RISK_ACK_VERSION = "wb-risk-2026-11-23"