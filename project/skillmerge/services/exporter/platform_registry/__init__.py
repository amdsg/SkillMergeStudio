"""Platform registry v2 public surface."""

from .counts import EvidenceCounts, RegistryCounts, build_evidence_counts, build_registry_counts
from .discovery_reader import grade, load_latest, load_round, summarize
from .loader import PlatformEntry, PlatformLoadResult, load_registry

__all__ = [
    "EvidenceCounts",
    "RegistryCounts",
    "PlatformEntry",
    "PlatformLoadResult",
    "build_evidence_counts",
    "build_registry_counts",
    "grade",
    "load_latest",
    "load_round",
    "summarize",
    "load_registry",
]