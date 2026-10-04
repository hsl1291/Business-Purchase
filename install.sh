#!/usr/bin/env bash
# Install bizbuy on macOS / Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/hsl1291/Business-Purchase/HEAD/install.sh | bash
#   (or download this file and run: bash install.sh)
#
# Clones the repo to ~/.bizbuy/app, creates a private Python environment in
# ~/.bizbuy/venv, links the `bizbuy` command into ~/.local/bin, and adds a
# BizBuy launcher (Mac: on the Desktop; Linux: in the applications menu).
# Re-running it is safe: an existing install is updated instead.
# Options: --launch (open the app when done)
# Env overrides: BIZBUY_HOME, BIZBUY_BRANCH, BIZBUY_REPO.
set -euo pipefail

LAUNCH=0
[ "${1:-}" = "--launch" ] && LAUNCH=1

REPO="${BIZBUY_REPO:-https://github.com/hsl1291/Business-Purchase.git}"
HOME_DIR="${BIZBUY_HOME:-$HOME/.bizbuy}"
APP="$HOME_DIR/app"
VENV="$HOME_DIR/venv"
BIN="$HOME/.local/bin"

die() { echo "error: $*" >&2; exit 1; }

find_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      echo "$c"; return
    fi
  done
}

# On a Mac with Homebrew, offer to install what's missing. (Apple's built-in
# python3 is 3.9, too old, so this matters even when python3 exists.)
if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null; then
  missing=""
  command -v git >/dev/null || missing="git"
  [ -n "$(find_python)" ] || missing="$missing python@3.12"
  if [ -n "$missing" ]; then
    read -r -p "Install $missing with Homebrew? [Y/n] " ans </dev/tty || ans=y
    case "$ans" in [nN]*) ;; *) brew install $missing ;; esac
  fi
fi

command -v git >/dev/null || die "git is required. Install it (macOS: xcode-select --install; Ubuntu: sudo apt install git) and re-run."

PY="$(find_python)"
[ -n "$PY" ] || die "Python 3.10+ is required. Install it from https://www.python.org/downloads/ and re-run."

mkdir -p "$HOME_DIR" "$BIN"
if [ -d "$APP/.git" ]; then
  echo "Existing install found; updating..."
  git -C "$APP" pull --ff-only
else
  echo "Cloning $REPO ..."
  if [ -n "${BIZBUY_BRANCH:-}" ]; then
    git clone --branch "$BIZBUY_BRANCH" "$REPO" "$APP"
  else
    git clone "$REPO" "$APP"
  fi
fi

[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
echo "Setting up the Python environment (first time takes a few minutes)..."
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -e "$APP"
ln -sf "$VENV/bin/bizbuy" "$BIN/bizbuy"

# Launcher
if [ "$(uname)" = "Darwin" ]; then
  LAUNCHER="$HOME/Desktop/BizBuy.command"
  mkdir -p "$HOME/Desktop"
  printf '#!/bin/bash\nexec "%s" gui\n' "$VENV/bin/bizbuy" > "$LAUNCHER"
  chmod +x "$LAUNCHER"
else
  LAUNCHER="$HOME/.local/share/applications/bizbuy.desktop"
  mkdir -p "$(dirname "$LAUNCHER")"
  cat > "$LAUNCHER" <<DESKTOP
[Desktop Entry]
Type=Application
Name=BizBuy
Comment=Find and value businesses to buy
Exec="$VENV/bin/bizbuy" gui
Terminal=true
Categories=Office;Finance;
DESKTOP
fi

echo
echo "Installed: $("$BIN/bizbuy" version)"
echo "Open it with the BizBuy launcher ($LAUNCHER) or by running: bizbuy gui"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "NOTE: add $BIN to your PATH, e.g.:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc  (or ~/.bashrc)";;
esac
echo "Update later: Settings & updates page in the app, or: bizbuy update"

if [ "$LAUNCH" = 1 ]; then
  echo "Opening BizBuy (keep this window open while you use it)..."
  exec "$VENV/bin/bizbuy" gui
fi
