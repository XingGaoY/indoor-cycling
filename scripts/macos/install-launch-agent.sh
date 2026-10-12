#!/bin/bash
# Install a per-user LaunchAgent for the simulator; requires interactive GUI session.
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS only" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="$HOME/.config/indoor-cycling/runtime.env"
if [[ ! -x "$ROOT/.venv/bin/indoor-cycling" || ! -r "$CONFIG" ]]; then
  echo "First create .venv, install the package and create $CONFIG (see doc/03)" >&2
  exit 1
fi
PLIST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/IndoorCycling"
PLIST="$PLIST_DIR/dev.indoorcycling.simulator.plist"
mkdir -p "$PLIST_DIR" "$LOG_DIR"
chmod 700 "$LOG_DIR"
python3 - "$PLIST" "$ROOT/scripts/macos/run-local.sh" "$ROOT" "$LOG_DIR" <<'PY'
from pathlib import Path
import plistlib
import sys
path, runner, root, logs = sys.argv[1:]
settings = {
    "Label": "dev.indoorcycling.simulator",
    "ProgramArguments": ["/bin/bash", runner],
    "WorkingDirectory": root,
    "RunAtLoad": True,
    "KeepAlive": {"SuccessfulExit": False},
    "StandardOutPath": str(Path(logs) / "stdout.log"),
    "StandardErrorPath": str(Path(logs) / "stderr.log"),
}
p = Path(path)
p.write_bytes(plistlib.dumps(settings))
p.chmod(0o600)
print(f"Wrote {p}")
PY
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed dev.indoorcycling.simulator in $DOMAIN (localhost-only)."
echo "Inspect with: launchctl print '$DOMAIN/dev.indoorcycling.simulator'"
