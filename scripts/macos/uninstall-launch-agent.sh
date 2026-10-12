#!/bin/bash
# Stop and remove only the simulator LaunchAgent; preserve user config and database.
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This uninstaller is for macOS only" >&2
  exit 1
fi
PLIST="$HOME/Library/LaunchAgents/dev.indoorcycling.simulator.plist"
if [[ -f "$PLIST" ]]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
  rm "$PLIST"
fi
echo "LaunchAgent removed; local database, token and source unchanged."
