#!/usr/bin/env bash
# Double-click this file in Finder to install (or update) BizBuy on a Mac.
# If macOS says it can't be opened, right-click it and choose Open.
cd "$(dirname "$0")" || exit 1
if [ ! -f install.sh ]; then
  echo "install.sh was not found next to this file. Download the whole BizBuy folder"
  echo "(GitHub: Code > Download ZIP), unzip it, and run this again."
else
  bash install.sh --launch
fi
echo
read -r -p "Press Return to close this window."
