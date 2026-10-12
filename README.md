# Indoor Cycling

Mac mini–hosted indoor cycling service with an installable phone dashboard. **This initial release uses a simulator for ALL remote controls: no Bluetooth writes and no real ERG control.**

## Requirements

- macOS + Python 3.11 or later for BLE diagnostics
- T300 powered on and COROS HR broadcast mode enabled for optional read-only inspection

## Quick start

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
export CYCLING_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
indoor-cycling serve
```

Open `http://127.0.0.1:8765` on Mac mini and enter the printed or separately saved `CYCLING_TOKEN`. The default server binds only to localhost. The demo PWA has no installable icon yet, and remote HTTPS access requires a trusted reverse proxy and further hardening; **do not expose the HTTP server directly to the internet or a shared LAN.**

## Read-only BLE diagnostics

```sh
indoor-cycling scan --seconds 10
indoor-cycling inspect '<identifier-from-scan>'
```

`inspect` reads GATT characteristics only where permitted; it does not write to control points. Never share device identifiers in public bug reports without redaction. On macOS grant Bluetooth permission to the Python/terminal process.

## Scope and current limitations

- Supported today: simulator status / start / pause / stop / bounded 40–150 W target, BLE scan and GATT inspection, decoding Heart Rate Measurement and FTMS Indoor Bike Data, SQLite training samples, minimal responsive page, CI tests.
- Not yet supported: real BLE telemetry subscriptions, hardware ERG writes, hardware safety watchdog, phone HTTPS deployment, FIT export, COROS upload, multi-user access, crash recovery or automated device reconnection.
- This is a development MVP, **not** production-safe exercise control software.
- The demonstration heart rate and power are synthetic; do not interpret as personal training data.

## Next milestones

1. Use diagnostics to capture *redacted* T300 firmware, FTMS characteristics, and power range; confirm COROS BLE heart-rate broadcast.
2. Add read-only live BLE subscriptions and freshness checks.
3. Implement a strictly guarded FTMS state machine and low-power hardware verification.
4. Deploy via macOS launchd behind authenticated HTTPS on the LAN.
5. Generate validated FIT and separately assess a supported COROS upload flow.
