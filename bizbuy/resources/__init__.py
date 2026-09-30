"""Bundled defaults (scoring config, NAICS benchmarks, sample data).

Commands look for a file in your workspace first (e.g. ./config/scoring.yaml,
created by `bizbuy init`) and fall back to the bundled copy, so edits you
make in your workspace win, and `bizbuy update` never overwrites them.
"""
from __future__ import annotations

from pathlib import Path

RESOURCE_DIR = Path(__file__).parent

# name -> path inside a workspace
WORKSPACE_PATHS = {
    "scoring.yaml": Path("config") / "scoring.yaml",
    "benchmarks.csv": Path("config") / "benchmarks.csv",
}


def default_path(name: str) -> str:
    local = WORKSPACE_PATHS.get(name)
    if local is not None and local.exists():
        return str(local)
    return str(RESOURCE_DIR / name)
