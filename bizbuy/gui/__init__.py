"""`bizbuy gui`: start the point-and-click app and open it in the browser."""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP = Path(__file__).with_name("app.py")


def free_port(preferred: int = 8501) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("no free port")


def _open_when_ready(url: str, port: int, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            webbrowser.open(url)
            return
        except OSError:
            time.sleep(0.5)


def auto_update_enabled(workspace: Path) -> bool:
    """On unless turned off with BIZBUY_NO_AUTO_UPDATE=1 or in the app's Settings page."""
    if os.environ.get("BIZBUY_NO_AUTO_UPDATE") == "1":
        return False
    settings = workspace / "config" / "app.yaml"
    try:
        import yaml
        return bool((yaml.safe_load(settings.read_text()) or {}).get("auto_update", True))
    except (OSError, ValueError):
        return True
    except Exception:  # malformed YAML: fail open, updates are the safe default
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bizbuy gui", description=__doc__)
    parser.add_argument("--workspace", help="Folder for your data (default: ~/BizBuy)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab")
    parser.add_argument("--no-update", action="store_true", help="Skip the automatic update check")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace or os.environ.get("BIZBUY_WORKSPACE") or Path.home() / "BizBuy").expanduser()
    if not args.no_update and auto_update_enabled(workspace):
        from bizbuy.update import auto_update

        print("Checking GitHub for updates...")
        status = auto_update()
        if status:
            print(status)

    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("The app needs Streamlit. Run `bizbuy update` (or re-run the installer).", file=sys.stderr)
        return 1

    env = dict(os.environ)
    if args.workspace:
        env["BIZBUY_WORKSPACE"] = str(Path(args.workspace).expanduser().resolve())
    port = free_port()
    url = f"http://localhost:{port}"
    print(f"BizBuy is running at {url}")
    print("Keep this window open while you use it. Close it (or press Ctrl+C) to quit.")
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url, port), daemon=True).start()

    cmd = [sys.executable, "-m", "streamlit", "run", str(APP),
           "--server.headless=true", f"--server.port={port}", "--server.address=127.0.0.1",
           "--browser.gatherUsageStats=false", "--theme.base=light",
           "--client.toolbarMode=minimal"]
    try:
        return subprocess.call(cmd, env=env)
    except KeyboardInterrupt:
        return 0
