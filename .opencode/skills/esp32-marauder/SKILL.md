---
name: esp32-marauder
description: "Control ESP32 Marauder via serial — WiFi scanning, deauth, beacon spam, probe flood, raw commands"
---

# ESP32 Marauder Serial Control

Send commands to ESP32 Marauder firmware via USB serial. Marauder commands are newline-terminated text; responses are line-buffered.

## Prerequisites

```bash
pip install pyserial
```

## ESP32 auto-detection

Detect the ESP32 Marauder USB port by matching known VID:PIDs:

| Chip | VID |
|------|-----|
| CP210x (Silicon Labs) | `0x10C4` |
| CH340 | `0x1A86` |
| ESP32-S2/S3 native USB | `0x303A` |

```bash
python3 -c "
import serial.tools.list_ports
ESP32_VIDS = [0x10C4, 0x1A86, 0x303A]
for port in serial.tools.list_ports.comports():
    if port.vid in ESP32_VIDS:
        print(f'ESP32 detected: {port.device} (VID={hex(port.vid)}, PID={hex(port.pid)})')
"
```

If auto-detection fails, set the port manually via `MARAUDER_PORT` env var, or use the typical macOS port: `/dev/cu.SLAB_USBtoUART` or `/dev/cu.usbserial-*`.

## Generic command helper

Use this pattern to send any Marauder command and read the response:

```bash
python3 -c "
import serial, serial.tools.list_ports, time, os

# Auto-detect or use env var
ESP32_VIDS = [0x10C4, 0x1A86, 0x303A]
port = os.environ.get('MARAUDER_PORT', '')
if not port:
    for p in serial.tools.list_ports.comports():
        if p.vid in ESP32_VIDS:
            port = p.device
            break
if not port:
    print('ERROR: ESP32 Marauder not found. Connect via USB or set MARAUDER_PORT.')
    exit(1)

ser = serial.Serial(port, 115200, timeout=1)
ser.write(b'COMMAND_HERE\n')
time.sleep(DURATION)
ser.write(b'stopscan\n')
time.sleep(1)
while ser.in_waiting:
    print(ser.readline().decode('utf-8', errors='ignore').strip())
ser.close()
"
```

Replace `COMMAND_HERE` and `DURATION` as needed for each operation.

## Scan WiFi access points

```bash
# Replace COMMAND_HERE with: scanap
# Replace DURATION with: 10  (seconds to scan)
```

Marauder command: `scanap`
Duration: 10 seconds recommended. Outputs discovered SSIDs, BSSIDs, channels, signal strength.

## Scan WiFi stations (clients)

```bash
# Replace COMMAND_HERE with: scansta
# Replace DURATION with: 10
```

Marauder command: `scansta`
Shows client devices connected to nearby APs.

## Deauth attack

**WARNING: Disruptive attack. Use only on authorized networks.**

```bash
# Replace COMMAND_HERE with: attack -t deauth
# Replace DURATION with: 10
```

Marauder command: `attack -t deauth`
Sends deauthentication frames to disconnect clients from APs. HIGH risk.

## Beacon spam

Broadcast fake WiFi SSIDs. HIGH risk.

- Random SSIDs: `attack -t beacon -r`
- Custom SSIDs: `attack -t beacon -l MyFakeAP,AnotherOne,FreeWiFi`

```bash
# Replace COMMAND_HERE with: attack -t beacon -r
# Replace DURATION with: 15
```

## Probe flood

Send probe request frames to trigger AP responses (active recon). HIGH risk.

```bash
# Replace COMMAND_HERE with: attack -t probe
# Replace DURATION with: 10
```

## Stop any running scan/attack

```bash
python3 -c "
import serial, os, serial.tools.list_ports
ESP32_VIDS = [0x10C4, 0x1A86, 0x303A]
port = os.environ.get('MARAUDER_PORT', '')
if not port:
    for p in serial.tools.list_ports.comports():
        if p.vid in ESP32_VIDS:
            port = p.device
            break
if port:
    ser = serial.Serial(port, 115200, timeout=1)
    ser.write(b'stopscan\n')
    import time; time.sleep(1)
    while ser.in_waiting:
        print(ser.readline().decode('utf-8', errors='ignore').strip())
    ser.close()
    print('Marauder stopped.')
else:
    print('ESP32 not found.')
"
```

## Send raw command

For any Marauder CLI command not covered above, use the generic helper with the raw command string. Common commands:

- `help` -- list all available commands
- `list ap` -- list scanned APs
- `list sta` -- list scanned stations
- `select ap N` -- select AP by index
- `select sta N` -- select station by index
- `ssid -a NAME` -- add SSID to list
- `ssid -r NAME` -- remove SSID from list
- `channel N` -- set channel

## Notes

- WiFi scanning (`scanap`, `scansta`) is MEDIUM risk.
- Deauth, beacon spam, and probe flood are HIGH risk -- disruptive attacks.
- `stopscan` is LOW risk -- stops all running operations.
- Raw commands are HIGH risk -- unrestricted Marauder CLI access.
- Always call `stopscan` after timed operations to stop the attack/scan.
- Serial baud rate is always 115200.
- Close the serial connection when done to release the port.
