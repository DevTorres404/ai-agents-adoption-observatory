"""Versioned analytical scope shared with the API through the same JSON file."""
import json
from pathlib import Path

SCOPE_PATH = Path(__file__).resolve().parents[2] / "config" / "observatory_scope.json"
SCOPE = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
SUPPORTED_AGENTS = tuple(SCOPE["agents"])
ACTIVE_SOURCES = frozenset(SCOPE["active_sources"])
INACTIVE_SOURCES = frozenset(SCOPE["inactive_sources"])

if len(SUPPORTED_AGENTS) != 10 or len(set(SUPPORTED_AGENTS)) != 10:
    raise ValueError("Observatory scope must contain exactly ten distinct agents")
if ACTIVE_SOURCES & INACTIVE_SOURCES:
    raise ValueError("Active and inactive sources must not overlap")
