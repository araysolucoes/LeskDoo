"""Validate tracked YAML files without running Docker or accessing services."""
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATHS = [*sorted((ROOT / ".github" / "workflows").glob("*.yml")),
         *sorted((ROOT / "deploy").glob("*.yml"))]
if not PATHS:
    raise SystemExit("No YAML files found")
for path in PATHS:
    # SafeLoader treats 'on' as a boolean under YAML 1.1; parsing still checks syntax.
    with path.open(encoding="utf-8") as stream:
        doc = yaml.safe_load(stream)
    if not isinstance(doc, dict):
        raise SystemExit(f"Invalid YAML mapping: {path}")
    print(f"OK {path.relative_to(ROOT)}")
print(f"Validated {len(PATHS)} YAML files")
