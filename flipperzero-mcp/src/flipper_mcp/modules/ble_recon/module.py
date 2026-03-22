"""BLE reconnaissance module for FlipperAgent MCP.

Uses Bleak (laptop's own Bluetooth adapter) to scan, enumerate, and interact
with BLE target devices — independent of the Flipper Zero's BLE radio.

The Flipper handles BLE spam/attacks. This module handles BLE intelligence:
scan → discover → enumerate GATT → read/write characteristics.
"""

import asyncio
from typing import Any, Dict, List, Optional, Sequence

from mcp.types import Tool, TextContent

from ..base_module import FlipperModule

# Known Apple Continuity protocol device types (for fingerprinting)
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

# MAC OUI prefixes for common IoT/device vendors (first 3 bytes)
_KNOWN_OUIS: Dict[str, str] = {
    "D4:F5:47": "Google",
    "58:CB:52": "Google",
    "A4:77:33": "Google Nest",
    "44:07:0B": "Google Chromecast",
    "AC:37:43": "HTC",
    "F0:27:2D": "Amazon Echo",
    "74:C2:46": "Amazon",
    "38:F7:3D": "Amazon",
    "68:37:E9": "Amazon Ring",
    "B0:FC:36": "Xiaomi",
    "7C:49:EB": "Xiaomi",
    "50:EC:50": "Samsung",
    "C0:97:27": "Samsung SmartThings",
    "D0:03:4B": "Apple",
    "A8:51:5B": "Apple",
    "3C:E0:72": "Apple",
    "E0:B5:5F": "Espressif (ESP32)",
    "24:62:AB": "Espressif (ESP32)",
    "AC:67:B2": "Espressif (ESP32)",
    "30:AE:A4": "Espressif (ESP32)",
}


def _lookup_oui(address: str) -> str:
    """Look up manufacturer from MAC OUI prefix."""
    if not address or len(address) < 8:
        return "Unknown"
    prefix = address[:8].upper()
    return _KNOWN_OUIS.get(prefix, "Unknown")


def _format_manufacturer_data(mfr_data: dict) -> str:
    """Format manufacturer-specific data from advertisement."""
    parts = []
    for company_id, data in mfr_data.items():
        # Apple = 0x004C = 76
        if company_id == 76:
            parts.append(f"Apple(0x004C): {data.hex()}")
            # Try to decode device type
            if len(data) >= 3 and data[0] == 0x07:
                model_id = int.from_bytes(data[1:3], "little")
                device_name = _APPLE_DEVICE_TYPES.get(model_id)
                if device_name:
                    parts[-1] += f" [{device_name}]"
        # Samsung = 0x0075 = 117
        elif company_id == 117:
            parts.append(f"Samsung(0x0075): {data.hex()}")
        # Microsoft = 0x0006 = 6
        elif company_id == 6:
            parts.append(f"Microsoft(0x0006): {data.hex()}")
        else:
            parts.append(f"0x{company_id:04X}: {data.hex()}")
    return "; ".join(parts) if parts else ""


class BLEReconModule(FlipperModule):
    """BLE reconnaissance via laptop Bluetooth — scan, enumerate GATT, read/write."""

    @property
    def name(self) -> str:
        return "ble_recon"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "BLE recon via laptop Bluetooth (Bleak): scan devices, enumerate GATT "
            "services/characteristics, read/write values"
        )

    def validate_environment(self) -> tuple[bool, str]:
        try:
            import bleak  # noqa: F401
            return True, ""
        except ImportError:
            return False, "bleak not installed. Run: pip install bleak"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="ble_scan",
                description=(
                    "Scan for nearby BLE devices using the laptop's Bluetooth adapter. "
                    "Returns device names, addresses, RSSI, manufacturer data, and service UUIDs. "
                    "Passive — does not connect to any device."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Scan duration in seconds (default: 5)",
                        },
                        "name_filter": {
                            "type": "string",
                            "description": "Filter by device name (case-insensitive substring match). Optional.",
                        },
                        "rssi_threshold": {
                            "type": "integer",
                            "default": -90,
                            "description": "Minimum RSSI to include (default: -90 dBm). Closer = higher number.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="ble_enumerate",
                description=(
                    "Connect to a BLE device and enumerate all GATT services, "
                    "characteristics, and their properties (read/write/notify). "
                    "This reveals the device's full BLE attack surface."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Device address (MAC on Linux, UUID on macOS) from ble_scan results",
                        },
                        "timeout": {
                            "type": "number",
                            "default": 10.0,
                            "description": "Connection timeout in seconds (default: 10)",
                        },
                    },
                    "required": ["address"],
                },
            ),
            Tool(
                name="ble_read_char",
                description=(
                    "Read a characteristic value from a connected BLE device. "
                    "Use ble_enumerate first to find readable characteristic UUIDs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Device address",
                        },
                        "uuid": {
                            "type": "string",
                            "description": "Characteristic UUID to read (e.g., '00002a00-0000-1000-8000-00805f9b34fb')",
                        },
                    },
                    "required": ["address", "uuid"],
                },
            ),
            Tool(
                name="ble_write_char",
                description=(
                    "Write a value to a BLE characteristic. WARNING: This can trigger "
                    "actions on the target device (movement, unlock, state change). "
                    "Use only on devices you are authorized to test."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Device address",
                        },
                        "uuid": {
                            "type": "string",
                            "description": "Characteristic UUID to write to",
                        },
                        "value": {
                            "type": "string",
                            "description": "Hex-encoded value to write (e.g., '01FF00' or 'hello' for ASCII)",
                        },
                        "is_hex": {
                            "type": "boolean",
                            "default": True,
                            "description": "If true, value is hex-encoded bytes. If false, value is UTF-8 text.",
                        },
                        "response": {
                            "type": "boolean",
                            "default": True,
                            "description": "Request write-with-response (True) or write-without-response (False)",
                        },
                    },
                    "required": ["address", "uuid", "value"],
                },
            ),
            Tool(
                name="ble_subscribe",
                description=(
                    "Subscribe to notifications from a BLE characteristic for a duration. "
                    "Returns all notification values received during the listening period."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Device address",
                        },
                        "uuid": {
                            "type": "string",
                            "description": "Characteristic UUID to subscribe to",
                        },
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Listen duration in seconds (default: 5)",
                        },
                    },
                    "required": ["address", "uuid"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        return await self._dispatch(tool_name, arguments, {
            "ble_scan": self._scan,
            "ble_enumerate": self._enumerate,
            "ble_read_char": self._read_char,
            "ble_write_char": self._write_char,
            "ble_subscribe": self._subscribe,
        }, "BLE error")

    async def _scan(self, args: dict) -> Sequence[TextContent]:
        from bleak import BleakScanner

        duration = min(args.get("duration", 5.0), 60.0)  # Cap at 60s
        name_filter = args.get("name_filter", "").lower()
        rssi_threshold = args.get("rssi_threshold", -90)

        # Deduplicate in-place to prevent unbounded growth in dense environments
        by_addr: Dict[str, tuple] = {}

        def _detection_callback(device, adv_data):
            if adv_data.rssi < rssi_threshold:
                return
            if name_filter and name_filter not in (device.name or "").lower():
                return
            key = device.address
            if key not in by_addr or adv_data.rssi > by_addr[key][1].rssi:
                by_addr[key] = (device, adv_data)

        scanner = BleakScanner(detection_callback=_detection_callback)
        await scanner.start()
        await asyncio.sleep(duration)
        await scanner.stop()

        if not by_addr:
            return [TextContent(type="text", text=f"BLE scan ({duration}s): no devices found")]

        # Sort by RSSI (strongest first)
        sorted_devices = sorted(by_addr.values(), key=lambda x: -x[1].rssi)

        lines = [f"BLE scan ({duration}s): {len(sorted_devices)} device(s)\n"]
        for device, adv in sorted_devices:
            name = device.name or "(unnamed)"
            vendor = _lookup_oui(device.address)
            line = f"  {name} | {device.address} | RSSI: {adv.rssi} dBm | Vendor: {vendor}"

            # Service UUIDs
            if adv.service_uuids:
                line += f"\n    Services: {', '.join(adv.service_uuids[:5])}"
                if len(adv.service_uuids) > 5:
                    line += f" (+{len(adv.service_uuids) - 5} more)"

            # Manufacturer data
            if adv.manufacturer_data:
                mfr = _format_manufacturer_data(adv.manufacturer_data)
                if mfr:
                    line += f"\n    Manufacturer: {mfr}"

            # TX power
            if adv.tx_power is not None:
                line += f"\n    TX Power: {adv.tx_power} dBm"

            lines.append(line)

        return [TextContent(type="text", text="\n".join(lines))]

    async def _enumerate(self, args: dict) -> Sequence[TextContent]:
        from bleak import BleakClient

        address = args["address"]
        timeout = args.get("timeout", 10.0)

        async with BleakClient(address, timeout=timeout) as client:
            if not client.is_connected:
                return [TextContent(type="text", text=f"Failed to connect to {address}")]

            lines = [
                f"BLE GATT enumeration: {address}",
                f"  MTU: {client.mtu_size}",
                "",
            ]

            writable_count = 0
            readable_count = 0
            notifiable_count = 0

            for service in client.services:
                lines.append(f"  Service: {service.uuid}")
                if service.description:
                    lines.append(f"    Description: {service.description}")

                for char in service.characteristics:
                    props = ", ".join(char.properties)
                    lines.append(f"    Char: {char.uuid} [{props}]")
                    if char.description:
                        lines.append(f"      Description: {char.description}")

                    if "read" in char.properties:
                        readable_count += 1
                    if "write" in char.properties or "write-without-response" in char.properties:
                        writable_count += 1
                    if "notify" in char.properties or "indicate" in char.properties:
                        notifiable_count += 1

                    for desc in char.descriptors:
                        lines.append(f"      Descriptor: {desc.uuid}")

            lines.append("")
            lines.append(f"  Summary: {readable_count} readable, {writable_count} writable, {notifiable_count} notifiable")

            if writable_count > 0:
                lines.append(f"  ⚠ {writable_count} writable characteristic(s) — potential attack surface")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _read_char(self, args: dict) -> Sequence[TextContent]:
        from bleak import BleakClient

        address = args["address"]
        uuid = args["uuid"]

        async with BleakClient(address, timeout=10.0) as client:
            value = await client.read_gatt_char(uuid)
            hex_val = value.hex()
            # Try to decode as UTF-8
            try:
                text_val = value.decode("utf-8")
                display = f"hex: {hex_val}\n  utf8: {text_val}"
            except (UnicodeDecodeError, ValueError):
                display = f"hex: {hex_val} ({len(value)} bytes)"

        return [TextContent(type="text", text=f"BLE read {uuid}:\n  {display}")]

    async def _write_char(self, args: dict) -> Sequence[TextContent]:
        from bleak import BleakClient

        address = args["address"]
        uuid = args["uuid"]
        value_str = args["value"]
        is_hex = args.get("is_hex", True)
        response = args.get("response", True)

        if is_hex:
            try:
                data = bytes.fromhex(value_str.replace(" ", ""))
            except ValueError:
                return [TextContent(type="text", text=f"Invalid hex value: {value_str}")]
        else:
            data = value_str.encode("utf-8")

        async with BleakClient(address, timeout=10.0) as client:
            await client.write_gatt_char(uuid, data, response=response)

        return [
            TextContent(
                type="text",
                text=f"BLE write to {uuid}: {data.hex()} ({len(data)} bytes, response={response})",
            )
        ]

    async def _subscribe(self, args: dict) -> Sequence[TextContent]:
        from bleak import BleakClient

        address = args["address"]
        uuid = args["uuid"]
        duration = args.get("duration", 5.0)

        notifications: List[bytes] = []

        def _callback(sender, data: bytearray):
            notifications.append(bytes(data))

        async with BleakClient(address, timeout=10.0) as client:
            await client.start_notify(uuid, _callback)
            await asyncio.sleep(duration)
            await client.stop_notify(uuid)

        if not notifications:
            return [TextContent(type="text", text=f"BLE subscribe {uuid}: no notifications received in {duration}s")]

        lines = [f"BLE subscribe {uuid}: {len(notifications)} notification(s) in {duration}s"]
        for i, data in enumerate(notifications[:20]):
            try:
                text = data.decode("utf-8")
                lines.append(f"  [{i}] {data.hex()} (utf8: {text})")
            except (UnicodeDecodeError, ValueError):
                lines.append(f"  [{i}] {data.hex()} ({len(data)} bytes)")
        if len(notifications) > 20:
            lines.append(f"  ... +{len(notifications) - 20} more")

        return [TextContent(type="text", text="\n".join(lines))]
