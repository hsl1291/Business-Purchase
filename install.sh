#!/usr/bin/env bash
# Install bizbuy on macOS / Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/hsl1291/Business-Purchase/HEAD/install.sh | bash
#   (or download this file and run: bash install.sh)
#
# Clones the repo to ~/.bizbuy/app, creates a private Python environment in
# ~/.bizbuy/venv, and links the `bizbuy` command into ~/.local/bin.
# Re-running it is safe: an existing install is updated instead.
# Env overrides: BIZBUY_HOME, BIZBUY_BRANCH, BIZBUY_REPO.
set -euo pipefail

REPO="${BIZBUY_REPO:-https://github.com/hsl1291/Business-Purchase.git}"
HOME_DIR="${BIZBUY_HOME:-$HOME/.bizbuy}"
APP="$HOME_DIR/app"
VENV="$HOME_DIR/venv"
BIN="$HOME/.local/bin"

die() { echo "error: $*" >&2; exit 1; }

command -v git >/dev/null || die "git is required. Install it (macOS: xcode-select --install; Ubuntu: sudo apt install git) and re-run."

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PY="$c"; break
  fi
done
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
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e "$APP"
ln -sf "$VENV/bin/bizbuy" "$BIN/bizbuy"

echo
echo "Installed: $("$BIN/bizbuy" version)"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "NOTE: add $BIN to your PATH, e.g.:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc  (or ~/.bashrc)";;
esac
echo "Get started:  bizbuy init ~/BizBuy && cd ~/BizBuy && bizbuy run samples/sample_raw_licenses.csv"
echo "Update later: bizbuy update"
