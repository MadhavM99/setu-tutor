"""Load KEY=VALUE lines from a local .env (gitignored) into os.environ for research scripts.

Values already set in the shell win. Nothing is printed or logged, so keys never reach output or reports.
"""
import os
from pathlib import Path


def load(path: Path) -> list[str]:
    """Returns the names (never the values) of the variables it set."""
    p = Path(path)
    if not p.is_file():
        return []
    set_names = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.removeprefix("export ").split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
            set_names.append(k)
    return set_names
