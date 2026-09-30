"""Self-update from git.

The installers clone this repository and install it in editable mode, so the
code you run *is* the git checkout. Updating is therefore a `git pull`:
code changes take effect immediately, and dependencies are reinstalled only
when requirements.txt changed.

If bizbuy was installed some other way (e.g. `pip install git+...`), there is
no checkout to pull, so it falls back to `pip install --upgrade git+<repo>`.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/hsl1291/Business-Purchase.git"
INSTALL_ROOT = Path(__file__).resolve().parent.parent


class UpdateError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        raise UpdateError("git is not installed or not on PATH.")
    if proc.returncode != 0:
        raise UpdateError(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def _file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def is_git_install(root: Path = INSTALL_ROOT) -> bool:
    return (root / ".git").exists()


def current_version(root: Path = INSTALL_ROOT) -> str:
    if not is_git_install(root):
        return "unknown (not a git install)"
    try:
        commit = _git(root, "rev-parse", "--short", "HEAD")
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
        date = _git(root, "log", "-1", "--format=%cd", "--date=short")
    except UpdateError:
        return "unknown"
    return f"{branch} @ {commit} ({date})"


def check(root: Path = INSTALL_ROOT) -> int:
    """Return how many commits the install is behind its upstream."""
    _git(root, "fetch", "--quiet")
    return int(_git(root, "rev-list", "--count", "HEAD..@{u}"))


def update_git_install(root: Path = INSTALL_ROOT, check_only: bool = False) -> str:
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise UpdateError(
            f"The install at {root} has local code edits, so a pull could "
            "clobber them. Commit or discard them (git -C <path> stash), then retry. "
            "(Your workspace files -- configs, CSVs, deals -- live elsewhere and are never touched.)"
        )

    behind = check(root)
    if behind == 0:
        return f"Already up to date: {current_version(root)}"
    if check_only:
        return f"{behind} update(s) available. Run `bizbuy update` to install."

    reqs = root / "requirements.txt"
    before = _file_hash(reqs)
    _git(root, "pull", "--ff-only", "--quiet")

    if _file_hash(reqs) != before:
        print("Dependencies changed; installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "-r", str(reqs)], check=True
        )
    return f"Updated {behind} commit(s). Now at {current_version(root)}"


def update_pip_install() -> str:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", f"git+{REPO_URL}"], check=True
    )
    return "Updated via pip."


def run_update(check_only: bool = False) -> int:
    try:
        if is_git_install():
            print(update_git_install(check_only=check_only))
        elif check_only:
            print("Not a git install; cannot check. Run `bizbuy update` to reinstall the latest.")
        else:
            print(update_pip_install())
    except (UpdateError, subprocess.CalledProcessError) as e:
        print(f"Update failed: {e}", file=sys.stderr)
        return 1
    return 0
