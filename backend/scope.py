"""Read the exact same scope registry packaged in the ETL image."""
import json
from pathlib import Path

path = Path(__file__).with_name("observatory_scope.json")
if not path.is_file():  # Local checkout; Docker copies the registry beside us.
    path = Path(__file__).resolve().parents[1] / "etl" / "config" / "observatory_scope.json"
SCOPE = json.loads(path.read_text(encoding="utf-8"))
SUPPORTED_AGENTS = tuple(SCOPE["agents"])
ACTIVE_SOURCES = tuple(SCOPE["active_sources"])
if len(SUPPORTED_AGENTS) != 10 or len(set(SUPPORTED_AGENTS)) != 10:
    raise ValueError("Expected ten distinct supported agents")
