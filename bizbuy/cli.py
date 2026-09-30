"""`bizbuy` command-line entry point.

    bizbuy init [DIR]          create a workspace with editable config + samples
    bizbuy run RAW_CSV         ingest -> score -> estimate in one step
    bizbuy callsheet CSV       top-N outreach sheet with reasons
    bizbuy value PNL_YAML      post-NDA valuation of one deal
    bizbuy deals DIR           compare several deals side by side
    bizbuy fieldmap RAW_CSV    draft the column mapping for a new license export
    bizbuy refit CSV           refit score weights from logged outreach results
    bizbuy ingest|score|estimate|enrich ...   individual pipeline steps
    bizbuy update [--check]    pull the latest version from git
    bizbuy version

Run `bizbuy <command> -h` for a command's options.
"""
from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

from bizbuy.resources import RESOURCE_DIR

# command -> (module, one-line help)
COMMANDS: dict[str, tuple[str, str]] = {
    "run": ("bizbuy.pipeline", "ingest -> score -> estimate in one step"),
    "callsheet": ("bizbuy.make_call_sheet", "top-N outreach sheet with reasons"),
    "value": ("bizbuy.valuation", "post-NDA valuation of one deal"),
    "deals": ("bizbuy.deal_tracker", "compare several deals side by side"),
    "fieldmap": ("bizbuy.suggest_field_map", "draft the column mapping for a license export"),
    "refit": ("bizbuy.refit_weights", "refit score weights from outreach results"),
    "ingest": ("bizbuy.ingest", "normalize a raw license CSV"),
    "score": ("bizbuy.score", "score and rank a normalized CSV"),
    "estimate": ("bizbuy.estimate", "rough value range from benchmarks"),
    "enrich": ("bizbuy.enrich", "add web-presence / real-estate signals"),
}


def init_workspace(target: Path) -> int:
    """Copy editable config and samples into a workspace directory. Never
    overwrites an existing file, so re-running it is safe."""
    copies = {
        RESOURCE_DIR / "scoring.yaml": target / "config" / "scoring.yaml",
        RESOURCE_DIR / "benchmarks.csv": target / "config" / "benchmarks.csv",
        RESOURCE_DIR / "samples": target / "samples",
    }
    for d in ("data/raw", "deals"):
        (target / d).mkdir(parents=True, exist_ok=True)

    for src, dst in copies.items():
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True,
                            copy_function=lambda s, d: None if Path(d).exists() else shutil.copy2(s, d))
        elif not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    print(f"Workspace ready at {target.resolve()}")
    print("  config/    your scoring weights, field mapping, and NAICS benchmarks (edit freely)")
    print("  data/raw/  put license exports here")
    print("  deals/     one P&L YAML per deal (see samples/sample_pnl.yaml)")
    print(f"\nNext: cd \"{target}\" && bizbuy run samples/sample_raw_licenses.csv")
    return 0


def usage() -> str:
    width = max(len(c) for c in COMMANDS)
    lines = ["usage: bizbuy <command> [options]", "", "commands:",
             f"  {'init'.ljust(width)}  create a workspace with editable config and samples"]
    lines += [f"  {name.ljust(width)}  {help_}" for name, (_, help_) in COMMANDS.items()]
    lines += [f"  {'update'.ljust(width)}  pull the latest version from git (--check to only look)",
              f"  {'version'.ljust(width)}  show the installed version"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        return init_workspace(Path(rest[0] if rest else "."))
    if cmd == "update":
        from bizbuy.update import run_update
        return run_update(check_only="--check" in rest)
    if cmd in ("version", "--version"):
        from bizbuy.update import current_version
        print(f"bizbuy {current_version()}")
        return 0
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'.\n\n{usage()}", file=sys.stderr)
        return 2

    module = importlib.import_module(COMMANDS[cmd][0])
    return module.main(rest) or 0


if __name__ == "__main__":
    sys.exit(main())
