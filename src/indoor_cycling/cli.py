import argparse
import asyncio
import os


def main():
    p = argparse.ArgumentParser(description="Indoor Cycling diagnostics and simulator")
    sub = p.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Read-only BLE scan")
    scan.add_argument("--seconds", type=float, default=8)
    inspect = sub.add_parser("inspect", help="Read-only GATT inspection")
    inspect.add_argument("identifier", help="CoreBluetooth device identifier from scan")
    serve = sub.add_parser("serve", help="Run simulator-only server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    if args.command in ("scan", "inspect"):
        from .ble import inspect as inspect_ble, scan as scan_ble
        asyncio.run(scan_ble(args.seconds) if args.command == "scan" else inspect_ble(args.identifier))
    else:
        if not os.environ.get("CYCLING_TOKEN"):
            p.error("Set CYCLING_TOKEN to a strong secret before starting the server")
        import uvicorn
        uvicorn.run("indoor_cycling.server:app", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
