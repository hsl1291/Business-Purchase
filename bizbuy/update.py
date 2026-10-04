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
import os
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/hsl1291/Business-Purchase.git"
INSTALL_ROOT = Path(__file__).resolve().parent.parent


class UpdateError(RuntimeError):
    pass


def _git(root: Path, *args: str, interactive: bool = True, timeout: float | None = None) -> str:
    env = None
    if not interactive:
        # Fail fast instead of waiting on a credential prompt nobody can see.
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False,
            env=env, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise UpdateError(f"git {args[0]} timed out")
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


def check(root: Path = INSTALL_ROOT, interactive: bool = True) -> int:
    """Return how many commits the install is behind its upstream."""
    _git(root, "fetch", "--quiet", interactive=interactive, timeout=None if interactive else 20)
    return int(_git(root, "rev-list", "--count", "HEAD..@{u}"))


def updates_available_quietly(root: Path = INSTALL_ROOT) -> int | None:
    """Background check for the app: never prompts, never raises.
    Returns commits behind, or None if it couldn't tell."""
    if not is_git_install(root):
        return None
    try:
        return check(root, interactive=False)
    except (UpdateError, ValueError, OSError):
        return None


def _is_dirty(root: Path) -> bool:
    return bool(_git(root, "status", "--porcelain", "--untracked-files=no"))


def _pull_and_sync(root: Path, interactive: bool = True) -> None:
    """Fast-forward to upstream; reinstall dependencies only if they changed."""
    reqs = root / "requirements.txt"
    before = _file_hash(reqs)
    _git(root, "pull", "--ff-only", "--quiet", interactive=interactive,
         timeout=None if interactive else 120)
    if _file_hash(reqs) != before:
        print("Dependencies changed; installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
             "-r", str(reqs)], check=True,
        )


def follow_default_branch(root: Path = INSTALL_ROOT, interactive: bool = True) -> str | None:
    """Switch the install to GitHub's default branch if it has moved.

    Installs should track whatever the repo's default branch is (e.g. after a
    feature branch is merged into main and deleted), not whichever branch was
    the default on install day. Returns the new branch name if it switched.
    """
    _git(root, "remote", "set-head", "origin", "--auto", interactive=interactive,
         timeout=None if interactive else 20)
    default = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")
    current = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if not default or default == current:
        return None
    _git(root, "checkout", "--quiet", "-B", default, "--track", f"origin/{default}")
    return default


def auto_update(root: Path = INSTALL_ROOT) -> str | None:
    """Run at app launch: bring the install up to date from GitHub.

    Never prompts and never raises: if GitHub can't be reached (offline, not
    signed in), it says so and the app opens on the version already installed.
    Returns a one-line status, or None if nothing needed saying.
    """
    if not is_git_install(root):
        return None
    try:
        if _is_dirty(root):
            return "Skipped automatic update: the install folder has local code edits."
        _git(root, "fetch", "--quiet", "--prune", interactive=False, timeout=20)
        switched = follow_default_branch(root, interactive=False)
        behind = int(_git(root, "rev-list", "--count", "HEAD..@{u}"))
        if behind:
            _pull_and_sync(root, interactive=False)
        if switched or behind:
            return f"Updated to the latest version: {current_version(root)}"
        return None
    except (UpdateError, ValueError, OSError, subprocess.CalledProcessError) as e:
        first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
        return f"Couldn't check GitHub for updates ({first_line}). Opening the installed version."


def update_git_install(root: Path = INSTALL_ROOT, check_only: bool = False) -> str:
    if _is_dirty(root):
        raise UpdateError(
            f"The install at {root} has local code edits, so a pull could "
            "clobber them. Commit or discard them (git -C <path> stash), then retry. "
            "(Your workspace files -- configs, CSVs, deals -- live elsewhere and are never touched.)"
        )

    behind = check(root)
    if not check_only:
        switched = follow_default_branch(root)
        if switched:
            behind = int(_git(root, "rev-list", "--count", "HEAD..@{u}"))
            if not behind:
                return f"Switched to the default branch. Now at {current_version(root)}"
    if behind == 0:
        return f"Already up to date: {current_version(root)}"
    if check_only:
        return f"{behind} update(s) available. Run `bizbuy update` to install."

    _pull_and_sync(root)
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
