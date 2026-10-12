"""Read-only BLE discovery and GATT diagnosis. No control-point writes."""
import asyncio
import json
from bleak import BleakClient, BleakScanner

FTMS = "00001826-0000-1000-8000-00805f9b34fb"
HR = "0000180d-0000-1000-8000-00805f9b34fb"

async def scan(seconds: float = 8) -> None:
    devices = await BleakScanner.discover(timeout=seconds, return_adv=True)
    for address, (device, adv) in devices.items():
        print(json.dumps({"identifier": address, "name": device.name, "service_uuids": adv.service_uuids,
                          "rssi": adv.rssi}, ensure_ascii=False))

async def inspect(identifier: str) -> None:
    # macOS identifiers are CoreBluetooth UUIDs, not hardware MACs.
    async with BleakClient(identifier, timeout=20) as client:
        for svc in client.services:
            print(f"SERVICE {svc.uuid} {svc.description}")
            for char in svc.characteristics:
                print(f"  CHAR {char.uuid} {char.properties} {char.description}")
                for descriptor in char.descriptors:
                    print(f"    DESC {descriptor.uuid}")
                if "read" in char.properties:
                    try:
                        value = await asyncio.wait_for(client.read_gatt_char(char), timeout=5)
                        print(f"    READ {bytes(value).hex()}")
                    except Exception as exc:
                        print(f"    READ_ERROR {type(exc).__name__}: {exc}")
