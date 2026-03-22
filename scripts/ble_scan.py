#!/usr/bin/env python3
"""BLE scan using the laptop's Bluetooth adapter (Bleak).

Outputs JSON to stdout with discovered devices, logs to stderr.

Usage:
    python3 scripts/ble_scan.py                         # 5s scan
    python3 scripts/ble_scan.py --duration 15           # 15s scan
    python3 scripts/ble_scan.py --name "lock"           # filter by name
    python3 scripts/ble_scan.py --rssi -70              # only strong signals
"""

import argparse
import asyncio
import json
import sys


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# Known Apple Continuity device types
_APPLE_DEVICE_TYPES = {
    0x0220: "AirPods Pro",
    0x0620: "AirPods Gen 3",
    0x0E20: "AirPods Pro Gen 2",
    0x1420: "AirPods Max",
    0x0320: "Powerbeats Pro",
    0x0520: "Beats Solo Pro",
    0x0A20: "Beats Fit Pro",
    0x0F20: "Beats Studio Buds+",
    0x1020: "Beats Studio Pro",
}

# MAC OUI prefixes for common vendors
_KNOWN_OUIS = {
    "D4:F5:47": "Google", "58:CB:52": "Google", "A4:77:33": "Google Nest",
    "44:07:0B": "Google Chromecast", "F0:27:2D": "Amazon Echo",
    "74:C2:46": "Amazon", "38:F7:3D": "Amazon", "68:37:E9": "Amazon Ring",
    "B0:FC:36": "Xiaomi", "7C:49:EB": "Xiaomi", "50:EC:50": "Samsung",
    "C0:97:27": "Samsung SmartThings", "D0:03:4B": "Apple",
    "A8:51:5B": "Apple", "3C:E0:72": "Apple", "E0:B5:5F": "Espressif (ESP32)",
    "24:62:AB": "Espressif (ESP32)", "AC:67:B2": "Espressif (ESP32)",
    "30:AE:A4": "Espressif (ESP32)",
}


def _lookup_oui(address: str) -> str:
    if not address or len(address) < 8:
        return "Unknown"
    return _KNOWN_OUIS.get(address[:8].upper(), "Unknown")


def _decode_manufacturer_data(mfr_data: dict) -> list:
    entries = []
    for company_id, data in mfr_data.items():
        entry = {"company_id": f"0x{company_id:04X}", "data_hex": data.hex()}
        if company_id == 76:  # Apple
            entry["vendor"] = "Apple"
            if len(data) >= 3 and data[0] == 0x07:
                model_id = int.from_bytes(data[1:3], "little")
                device_name = _APPLE_DEVICE_TYPES.get(model_id)
                if device_name:
                    entry["device_type"] = device_name
        elif company_id == 117:
            entry["vendor"] = "Samsung"
        elif company_id == 6:
            entry["vendor"] = "Microsoft"
        entries.append(entry)
    return entries


async def _scan(args: argparse.Namespace) -> int:
    try:
        from bleak import BleakScanner
    except ImportError:
        _log("ERROR: bleak not installed. Run: pip install bleak")
        print(json.dumps({"error": "bleak not installed"}))
        return 1

    duration = min(args.duration, 120.0)
    name_filter = (args.name or "").lower()
    rssi_threshold = args.rssi

    _log(f"Scanning BLE for {duration}s (RSSI >= {rssi_threshold} dBm)...")

    by_addr = {}

    def _callback(device, adv_data):
        if adv_data.rssi < rssi_threshold:
            return
        if name_filter and name_filter not in (device.name or "").lower():
            return
        key = device.address
        if key not in by_addr or adv_data.rssi > by_addr[key][1].rssi:
            by_addr[key] = (device, adv_data)

    scanner = BleakScanner(detection_callback=_callback)
    await scanner.start()
    await asyncio.sleep(duration)
    await scanner.stop()

    _log(f"Scan complete. {len(by_addr)} device(s) found.")

    devices = []
    for device, adv in sorted(by_addr.values(), key=lambda x: -x[1].rssi):
        entry = {
            "name": device.name or None,
            "address": device.address,
            "rssi": adv.rssi,
            "vendor": _lookup_oui(device.address),
        }
        if adv.service_uuids:
            entry["service_uuids"] = adv.service_uuids
        if adv.manufacturer_data:
            entry["manufacturer_data"] = _decode_manufacturer_data(adv.manufacturer_data)
        if adv.tx_power is not None:
            entry["tx_power"] = adv.tx_power
        devices.append(entry)

    result = {
        "scan_duration_s": duration,
        "device_count": len(devices),
        "rssi_threshold": rssi_threshold,
        "devices": devices,
    }
    if name_filter:
        result["name_filter"] = name_filter

    print(json.dumps(result, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="BLE scan via laptop Bluetooth (Bleak)")
    parser.add_argument("--duration", type=float, default=5.0, help="Scan duration in seconds (default: 5)")
    parser.add_argument("--name", type=str, default=None, help="Filter by device name (case-insensitive substring)")
    parser.add_argument("--rssi", type=int, default=-90, help="Minimum RSSI threshold in dBm (default: -90)")
    args = parser.parse_args()
    rc = asyncio.run(_scan(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
