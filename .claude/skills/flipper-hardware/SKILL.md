---
name: flipper-hardware
description: "Control a Flipper Zero and scan BLE targets for authorized security research. Use when asked to interact with Flipper hardware, scan BLE devices, or control RF/IR/NFC/RFID."
---

# Flipper Hardware Control

All Flipper interaction is via Python scripts executed through Bash. You do NOT have MCP tool access. Run scripts from the project root.

The venv Python is at `flipperzero-mcp/.venv/bin/python`. Use `python3` for scripts (they add the MCP library to sys.path themselves).

## Connection & Device Info

```bash
# Get device info (JSON)
python3 scripts/flipper_connect.py

# Run any CLI command on the Flipper
python3 scripts/flipper_connect.py cli <command>
```

Environment variables for transport: `FLIPPER_TRANSPORT` (auto/usb/wifi), `FLIPPER_PORT`, `FLIPPER_WIFI_HOST`, `FLIPPER_WIFI_PORT`.

## BLE Scanning (Laptop Bluetooth via Bleak)

```bash
# Quick scan (5s default)
python3 scripts/ble_scan.py

# Longer scan with filters
python3 scripts/ble_scan.py --duration 15 --rssi -70 --name "lock"
```

Output: JSON with `devices[]` array, each entry has `name`, `address`, `rssi`, `vendor`, `service_uuids`, `manufacturer_data`.

## BLE GATT Enumeration

```bash
# Enumerate all services/characteristics for a target
python3 scripts/ble_enumerate.py AA:BB:CC:DD:EE:FF
python3 scripts/ble_enumerate.py AA:BB:CC:DD:EE:FF --timeout 15
```

Output: JSON with `services[]` array containing `characteristics[]` with `properties` (read/write/notify). Summary includes `writable` count = attack surface.

## Flipper Storage (SD Card)

```bash
python3 scripts/flipper_storage.py list /ext
python3 scripts/flipper_storage.py list /ext/subghz
python3 scripts/flipper_storage.py read /ext/subghz/signal.sub
python3 scripts/flipper_storage.py write /ext/test.txt "content here"
python3 scripts/flipper_storage.py mkdir /ext/my_dir
python3 scripts/flipper_storage.py info /ext
```

Path rules: must start with `/ext/` (SD card). `/int/` is blocked. No `..` traversal. No `.key`/`.priv`/`.secret` files.

## Flipper CLI Command Reference

Run any of these via `python3 scripts/flipper_connect.py cli <command>`:

| Category | Commands |
|----------|----------|
| **System** | `device_info`, `date`, `uptime`, `power info`, `power reboot`, `free` |
| **LED/Vibro** | `led set R G B` (0-255), `vibro 1`, `vibro 0` |
| **GPIO** | `gpio set <pin> <0\|1>`, `gpio read <pin>`, `gpio mode <pin> <mode>` |
| **SubGHz** | `subghz rx <freq_hz>`, `subghz tx <freq_hz> <data>`, `subghz decode_raw <file>` |
| **IR** | `ir rx`, `ir tx <protocol> <address> <command>`, `ir tx_raw <freq> <duty> <data>` |
| **NFC** | `nfc detect`, `nfc emulate <file>`, `nfc field` |
| **RFID** | `rfid read`, `rfid emulate <type> <data>`, `rfid write <type> <data>` |
| **BadUSB** | `badusb list`, `badusb execute <file>` |
| **Apps** | `apps list`, `apps launch <app_name>` |
| **Music** | `music_player play <file>` |
| **Storage** | `storage list <path>`, `storage read <path>`, `storage write <path> <content>` |

## Risk Classification & Safety Gates

| Risk Level | Action Required | Example Tools |
|------------|----------------|---------------|
| **LOW** | Proceed automatically | `ble_scan`, `device_info`, `storage_list`, `storage_read`, `nfc_detect`, `rfid_read`, `gpio_read`, `led_set`, `subghz_rx`, `ir_rx` |
| **MEDIUM** | Log rationale to stderr before executing | `ble_enumerate`, `ble_read_char`, `storage_write`, `ir_tx`, `gpio_set`, `apps_launch`, `ble_subscribe` |
| **HIGH** | Ask the user for explicit confirmation | `ble_write_char`, `subghz_tx`, `nfc_emulate`, `rfid_emulate`, `rfid_write`, `badusb_execute` |
| **BLOCKED** | Never execute | Writing to `/int/`, accessing `.key`/`.priv` files |

For HIGH-risk actions: state what you intend to do, the target, and why, then wait for user confirmation before running the command.

## Usage Examples

### Example 1: Discover nearby BLE devices
```bash
python3 scripts/ble_scan.py --duration 10 --rssi -75
```
Parse the JSON output. For interesting devices, enumerate GATT:
```bash
python3 scripts/ble_enumerate.py <address_from_scan>
```

### Example 2: Check Flipper status and list stored signals
```bash
python3 scripts/flipper_connect.py
python3 scripts/flipper_storage.py list /ext/subghz
```

### Example 3: Capture IR signals
```bash
python3 scripts/flipper_connect.py cli ir rx
```
Wait for the response, which contains captured protocol/address/command data.
