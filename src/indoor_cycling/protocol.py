"""Read-only parsers for standard Bluetooth SIG characteristics."""
from __future__ import annotations


def heart_rate_measurement(data: bytes) -> int:
    if len(data) < 2:
        raise ValueError("Heart Rate Measurement truncated")
    if data[0] & 1:
        if len(data) < 3:
            raise ValueError("16-bit heart rate truncated")
        return int.from_bytes(data[1:3], "little")
    return data[1]


def indoor_bike_data(data: bytes) -> dict[str, float]:
    if len(data) < 2:
        raise ValueError("Indoor Bike Data truncated")
    flags = int.from_bytes(data[:2], "little")
    p = 2
    result: dict[str, float] = {}
    def take(size: int, signed: bool = False) -> int:
        nonlocal p
        if len(data) < p + size:
            raise ValueError("Indoor Bike Data truncated")
        value = int.from_bytes(data[p:p+size], "little", signed=signed)
        p += size
        return value
    # FTMS: speed is present when bit 0 is clear; other listed fields when bit set.
    if not flags & (1 << 0):
        result["speed_kmh"] = take(2) / 100
    if flags & (1 << 1):
        result["avg_speed_kmh"] = take(2) / 100
    if flags & (1 << 2):
        result["cadence_rpm"] = take(2) / 2
    if flags & (1 << 3):
        result["avg_cadence_rpm"] = take(2) / 2
    if flags & (1 << 4):
        result["distance_m"] = take(3)
    if flags & (1 << 5):
        result["resistance_level"] = take(2, signed=True)
    if flags & (1 << 6):
        result["power_w"] = take(2, signed=True)
    if flags & (1 << 7):
        result["avg_power_w"] = take(2, signed=True)
    if flags & (1 << 8):
        take(2); take(2); take(1)  # total, per-hour, per-minute energy
    if flags & (1 << 9):
        result["heart_rate_bpm"] = take(1)
    if flags & (1 << 10):
        result["metabolic_equivalent"] = take(1) / 10
    if flags & (1 << 11):
        result["elapsed_s"] = take(2)
    if flags & (1 << 12):
        result["remaining_s"] = take(2)
    return result
