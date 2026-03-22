#!/usr/bin/env python3
"""Deterministic campaign automation scripts.

These replace multi-step model reasoning with single script calls.
The model decides WHAT to run. The script handles HOW.

Usage:
    python3 scripts/campaign_auto.py recon [--duration 10]
    python3 scripts/campaign_auto.py enumerate <address>
    python3 scripts/campaign_auto.py probe-auth <address> <char_uuid>
    python3 scripts/campaign_auto.py device-info
    python3 scripts/campaign_auto.py full-scan [--duration 10]

All output is structured JSON to stdout. Logs go to stderr.
"""

import argparse
import asyncio
import json
import sys
import time

# Add MCP server to path
sys.path.insert(0, "flipperzero-mcp/src")


def _save_state(results, command):
    """Auto-save results to engagement_state.json.

    Best-effort — failures print a warning to stderr but don't block output.
    """
    try:
        from flipper_mcp.core.session import SessionManager

        sm = SessionManager(".")
        state = sm.load()
        if state is None:
            sm.new_engagement()

        if command == "recon":
            for dev in results.get("ble_devices", []):
                sm.update_or_add_target({
                    "name": dev.get("name"),
                    "address": dev.get("address"),
                    "type": "ble_device",
                    "rssi": dev.get("rssi"),
                    "metadata": {
                        "service_uuids": dev.get("service_uuids", []),
                        "manufacturer_ids": dev.get("manufacturer_ids", []),
                    },
                })
            if results.get("flipper") and not results["flipper"].get("error"):
                sm.update_notes(
                    sm.state.notes + f"\n[recon] Flipper info: {json.dumps(results['flipper'])}"
                )

        elif command == "enumerate":
            attack_surface = results.get("attack_surface", {})
            sm.update_or_add_target({
                "address": results.get("address"),
                "type": "ble_device",
                "attack_surface": {
                    "writable": attack_surface.get("writable", 0),
                    "readable": attack_surface.get("readable", 0),
                    "notifiable": attack_surface.get("notifiable", 0),
                },
                "mtu": results.get("mtu"),
                "services_count": len(results.get("services", [])),
            })

        elif command == "probe-auth":
            severity = "high" if results.get("auth_required") is False else "info"
            sm.add_vulnerability({
                "type": "auth_probe",
                "severity": severity,
                "address": results.get("address"),
                "characteristic": results.get("characteristic"),
                "auth_required": results.get("auth_required"),
                "result": results.get("result"),
            })

        elif command == "device-info":
            sm.update_notes(
                sm.state.notes + f"\n[device-info] Flipper firmware: {json.dumps(results)}"
            )

        elif command == "full-scan":
            for dev in results.get("devices", []):
                target = {
                    "name": dev.get("name"),
                    "address": dev.get("address"),
                    "type": "ble_device",
                    "rssi": dev.get("rssi"),
                }
                if "writable_characteristics" in dev:
                    target["attack_surface"] = {
                        "writable": dev.get("writable_characteristics", 0),
                    }
                if "mtu" in dev:
                    target["mtu"] = dev["mtu"]
                sm.update_or_add_target(target)
                if dev.get("enumerate_error"):
                    sm.add_vulnerability({
                        "type": "enumerate_error",
                        "severity": "info",
                        "address": dev.get("address"),
                        "result": dev["enumerate_error"],
                    })

    except Exception as e:
        print(f"State save warning: {e}", file=sys.stderr)


async def cmd_recon(args):
    """Full BLE + Flipper recon in one call."""
    from bleak import BleakScanner
    from flipper_mcp.core.server import FlipperMCPServer

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ble_devices": [],
        "flipper": None,
    }

    # BLE scan
    print("Scanning BLE...", file=sys.stderr)
    by_addr = {}

    def cb(device, adv_data):
        key = device.address
        if adv_data.rssi >= args.rssi:
            if key not in by_addr or adv_data.rssi > by_addr[key][1].rssi:
                by_addr[key] = (device, adv_data)

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    await asyncio.sleep(args.duration)
    await scanner.stop()

    for device, adv in sorted(by_addr.values(), key=lambda x: -x[1].rssi):
        entry = {
            "name": device.name or "(unnamed)",
            "address": device.address,
            "rssi": adv.rssi,
            "service_uuids": adv.service_uuids,
            "manufacturer_ids": list(adv.manufacturer_data.keys()),
        }
        results["ble_devices"].append(entry)

    # Flipper device info
    print("Connecting to Flipper...", file=sys.stderr)
    try:
        s = FlipperMCPServer({"transport": {"type": "usb", "usb": {}}})
        await s.initialize()
        info = await s.flipper.get_device_info()
        results["flipper"] = info
    except Exception as e:
        results["flipper"] = {"error": str(e)}

    print(json.dumps(results, indent=2))
    _save_state(results, "recon")


async def cmd_enumerate(args):
    """Full GATT enumeration of a BLE target."""
    from bleak import BleakClient

    results = {
        "address": args.address,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "services": [],
        "attack_surface": {"writable": 0, "readable": 0, "notifiable": 0},
    }

    print(f"Connecting to {args.address}...", file=sys.stderr)
    async with BleakClient(args.address, timeout=15.0) as client:
        results["mtu"] = client.mtu_size

        for service in client.services:
            svc = {
                "uuid": service.uuid,
                "description": service.description or "",
                "characteristics": [],
            }
            for char in service.characteristics:
                ch = {
                    "uuid": char.uuid,
                    "description": char.description or "",
                    "properties": list(char.properties),
                }
                if "read" in char.properties:
                    results["attack_surface"]["readable"] += 1
                    try:
                        value = await client.read_gatt_char(char)
                        ch["value_hex"] = value.hex()
                        ch["value_len"] = len(value)
                        try:
                            ch["value_text"] = value.decode("utf-8")
                        except (UnicodeDecodeError, ValueError):
                            pass
                    except Exception as e:
                        ch["read_error"] = str(e)

                if "write" in char.properties or "write-without-response" in char.properties:
                    results["attack_surface"]["writable"] += 1
                if "notify" in char.properties or "indicate" in char.properties:
                    results["attack_surface"]["notifiable"] += 1

                svc["characteristics"].append(ch)
            results["services"].append(svc)

    print(json.dumps(results, indent=2))
    _save_state(results, "enumerate")


async def cmd_probe_auth(args):
    """Probe whether a writable characteristic requires authentication."""
    from bleak import BleakClient

    results = {
        "address": args.address,
        "characteristic": args.char_uuid,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    print(f"Probing {args.char_uuid} on {args.address}...", file=sys.stderr)
    async with BleakClient(args.address, timeout=10.0) as client:
        try:
            await client.write_gatt_char(args.char_uuid, bytes([0x00]), response=True)
            results["auth_required"] = False
            results["result"] = "WRITE SUCCEEDED — no authentication required"
        except Exception as e:
            error = str(e)
            if "uthenticat" in error.lower():
                results["auth_required"] = True
                results["result"] = "AUTHENTICATION REQUIRED"
            elif "ncrypt" in error.lower():
                results["auth_required"] = True
                results["result"] = "ENCRYPTION REQUIRED"
            else:
                results["auth_required"] = None
                results["result"] = f"REJECTED: {error}"
            results["error"] = error

    print(json.dumps(results, indent=2))
    _save_state(results, "probe-auth")


async def cmd_device_info(args):
    """Get Flipper device info."""
    from flipper_mcp.core.server import FlipperMCPServer

    s = FlipperMCPServer({"transport": {"type": "usb", "usb": {}}})
    await s.initialize()
    info = await s.flipper.get_device_info()

    # Also list SD card
    try:
        files = await s.flipper.storage.list("/ext")
        info["sd_card_contents"] = files
    except Exception:
        pass

    # Also list installed apps
    try:
        apps_result = await s.flipper.run_cli("loader list")
        info["installed_apps"] = apps_result
    except Exception:
        pass

    print(json.dumps(info, indent=2))
    _save_state(info, "device-info")


async def cmd_full_scan(args):
    """Full scan: BLE + enumerate every named device + Flipper info."""
    from bleak import BleakScanner, BleakClient

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scan_duration": args.duration,
        "devices": [],
    }

    # Scan
    print("Scanning BLE...", file=sys.stderr)
    by_addr = {}

    def cb(device, adv_data):
        if adv_data.rssi >= args.rssi:
            key = device.address
            if key not in by_addr or adv_data.rssi > by_addr[key][1].rssi:
                by_addr[key] = (device, adv_data)

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    await asyncio.sleep(args.duration)
    await scanner.stop()

    # Enumerate each NAMED device
    for device, adv in sorted(by_addr.values(), key=lambda x: -x[1].rssi):
        entry = {
            "name": device.name or "(unnamed)",
            "address": device.address,
            "rssi": adv.rssi,
            "manufacturer_ids": list(adv.manufacturer_data.keys()),
            "service_uuids": adv.service_uuids,
        }

        if device.name and "flipper" not in (device.name or "").lower():
            print(f"Enumerating {device.name}...", file=sys.stderr)
            try:
                async with BleakClient(device.address, timeout=8.0) as client:
                    entry["mtu"] = client.mtu_size
                    entry["services"] = []
                    writable = 0
                    for svc in client.services:
                        for ch in svc.characteristics:
                            if "write" in ch.properties or "write-without-response" in ch.properties:
                                writable += 1
                    entry["writable_characteristics"] = writable
            except Exception as e:
                entry["enumerate_error"] = str(e)

        results["devices"].append(entry)

    print(json.dumps(results, indent=2))
    _save_state(results, "full-scan")


def main():
    parser = argparse.ArgumentParser(description="FlipperAgent campaign automation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_recon = sub.add_parser("recon", help="Full BLE + Flipper recon")
    p_recon.add_argument("--duration", type=float, default=10.0)
    p_recon.add_argument("--rssi", type=int, default=-90)

    p_enum = sub.add_parser("enumerate", help="Enumerate BLE target GATT")
    p_enum.add_argument("address", help="BLE device address")

    p_probe = sub.add_parser("probe-auth", help="Probe write auth on characteristic")
    p_probe.add_argument("address", help="BLE device address")
    p_probe.add_argument("char_uuid", help="Characteristic UUID")

    p_info = sub.add_parser("device-info", help="Flipper device info")

    p_full = sub.add_parser("full-scan", help="Scan + enumerate all named devices")
    p_full.add_argument("--duration", type=float, default=10.0)
    p_full.add_argument("--rssi", type=int, default=-85)

    args = parser.parse_args()

    commands = {
        "recon": cmd_recon,
        "enumerate": cmd_enumerate,
        "probe-auth": cmd_probe_auth,
        "device-info": cmd_device_info,
        "full-scan": cmd_full_scan,
    }

    asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    main()
