#!/usr/bin/env python3
"""Enumerate GATT services and characteristics for a BLE target.

Connects to a device, discovers all services/characteristics/descriptors,
and outputs structured JSON to stdout.

Usage:
    python3 scripts/ble_enumerate.py AA:BB:CC:DD:EE:FF
    python3 scripts/ble_enumerate.py AA:BB:CC:DD:EE:FF --timeout 15
"""

import argparse
import asyncio
import json
import sys


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


async def _enumerate(args: argparse.Namespace) -> int:
    try:
        from bleak import BleakClient
    except ImportError:
        _log("ERROR: bleak not installed. Run: pip install bleak")
        print(json.dumps({"error": "bleak not installed"}))
        return 1

    address = args.address
    timeout = args.timeout

    _log(f"Connecting to {address} (timeout={timeout}s)...")

    try:
        async with BleakClient(address, timeout=timeout) as client:
            if not client.is_connected:
                _log(f"ERROR: Failed to connect to {address}")
                print(json.dumps({"error": f"Failed to connect to {address}"}))
                return 1

            _log(f"Connected. MTU={client.mtu_size}. Enumerating GATT...")

            services_out = []
            total_readable = 0
            total_writable = 0
            total_notifiable = 0

            for service in client.services:
                svc = {
                    "uuid": service.uuid,
                    "description": service.description or None,
                    "characteristics": [],
                }

                for char in service.characteristics:
                    props = list(char.properties)
                    c = {
                        "uuid": char.uuid,
                        "description": char.description or None,
                        "properties": props,
                        "descriptors": [
                            {"uuid": d.uuid, "description": getattr(d, "description", None)}
                            for d in char.descriptors
                        ],
                    }
                    svc["characteristics"].append(c)

                    if "read" in props:
                        total_readable += 1
                    if "write" in props or "write-without-response" in props:
                        total_writable += 1
                    if "notify" in props or "indicate" in props:
                        total_notifiable += 1

                services_out.append(svc)

            result = {
                "address": address,
                "mtu": client.mtu_size,
                "services": services_out,
                "summary": {
                    "service_count": len(services_out),
                    "readable": total_readable,
                    "writable": total_writable,
                    "notifiable": total_notifiable,
                },
            }

            if total_writable > 0:
                result["summary"]["attack_surface_note"] = (
                    f"{total_writable} writable characteristic(s) found — potential attack surface"
                )

            print(json.dumps(result, indent=2))
            _log("Enumeration complete.")
            return 0

    except Exception as e:
        _log(f"ERROR: {e}")
        print(json.dumps({"error": str(e), "address": address}))
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Enumerate BLE GATT services/characteristics")
    parser.add_argument("address", help="BLE device address (MAC on Linux, UUID on macOS)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Connection timeout in seconds (default: 10)")
    args = parser.parse_args()
    rc = asyncio.run(_enumerate(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
