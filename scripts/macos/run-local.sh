#!/bin/bash
# LaunchAgent entrypoint: simulator only, localhost only.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="$HOME/.config/indoor-cycling/runtime.env"
if [[ ! -r "$CONFIG" ]]; then
  echo "Missing readable configuration: $CONFIG" >&2
  exit 1
fi
set -a
# Controlled by local owner: file must not be copied from untrusted sources.
source "$CONFIG"
set +a
if [[ -z "${CYCLING_TOKEN:-}" ]]; then
  echo "CYCLING_TOKEN is not configured" >&2
  exit 1
fi
if [[ ! -x "$ROOT/.venv/bin/indoor-cycling" ]]; then
  echo "Install package into $ROOT/.venv first" >&2
  exit 1
fi
exec "$ROOT/.venv/bin/indoor-cycling" serve --host 127.0.0.1 --port "${CYCLING_PORT:-8765}"
