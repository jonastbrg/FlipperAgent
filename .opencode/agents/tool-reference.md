---
description: Complete reference for all FlipperAgent tools, CLI commands, and hardware capabilities
mode: subagent
hidden: true
permission:
  edit: deny
  bash: deny
---

# FlipperAgent Tool Reference

## Flipper Zero CLI Commands

These are the raw CLI commands sent to the Flipper via the CLI bridge. The MCP tools wrap these, but you can also use them via `scripts/flipper_connect.py cli "command"`.

### System
| Command | What it does |
|---------|-------------|
| `device_info` | Full device info (50+ fields) |
| `power info` | Battery/power status |
| `power off` | Shutdown |
| `power reboot` | Reboot |
| `bt hci_info` | Bluetooth HCI info |
| `date` | Current date/time |
| `free` | Memory usage |
| `ps` | Running processes |
| `loader list` | List installed apps |
| `loader open {app}` | Launch app |

### LED / Vibro
| Command | What it does |
|---------|-------------|
| `led r {0-255}` | Red LED |
| `led g {0-255}` | Green LED |
| `led b {0-255}` | Blue LED |
| `led bl {0-255}` | Backlight |
| `vibro {0\|1}` | Vibration motor |

### Sub-GHz
| Command | What it does |
|---------|-------------|
| `subghz tx {hex_key} {freq} {te} {count}` | Transmit signal |
| `subghz rx {freq}` | Receive (blocks until Ctrl+C) |
| `subghz rx_raw {freq}` | Receive raw |
| `subghz decode_raw {file}` | Decode .sub file |
| `subghz tx_from_file {file} {repeat}` | Transmit from .sub |

### Infrared
| Command | What it does |
|---------|-------------|
| `ir tx {protocol} {address} {command}` | Transmit IR signal |
| `ir tx RAW F:{freq} DC:{duty} {samples}` | Transmit raw IR |
| `ir rx` | Receive IR (blocks) |

### NFC
| Command | What it does |
|---------|-------------|
| `nfc detect` | Detect NFC tag (blocks) |
| `nfc emulate` | Emulate NFC card (blocks) |
| `nfc field` | Activate NFC field |

### RFID (125kHz)
| Command | What it does |
|---------|-------------|
| `lfrfid read` | Read RFID tag (note: `lfrfid` not `rfid`) |
| `lfrfid emulate {type} {data}` | Emulate RFID tag |
| `lfrfid write {type} {data}` | Write to RFID tag |

### GPIO
| Command | What it does |
|---------|-------------|
| `gpio read {pin}` | Read pin (PA7, PA6, PA4, PB3, PB2, PC3, PC1, PC0) |
| `gpio set {pin} {0\|1}` | Set pin output |
| `gpio mode {pin} {0\|1}` | Set mode (0=input, 1=output) |

### Storage
| Command | What it does |
|---------|-------------|
| `storage list {path}` | List directory |
| `storage read {path}` | Read file |
| `storage stat {path}` | File stats |
| `storage mkdir {path}` | Create directory |
| `storage remove {path}` | Delete file |

## BLE (Bleak on Laptop)

BLE operations use the LAPTOP's Bluetooth adapter, NOT the Flipper. Use the MCP tools or wrapper scripts:

```bash
python3 scripts/ble_scan.py --duration 10 --rssi -80
python3 scripts/ble_enumerate.py "DEVICE_ADDRESS"
```

### Common BLE Service UUIDs
| UUID | Service |
|------|---------|
| 0x1800 | Generic Access |
| 0x1801 | Generic Attribute |
| 0x180A | Device Information |
| 0x180D | Heart Rate |
| 0x180F | Battery Service |
| 0xFE59 | Nordic DFU |

### GATT Characteristic Properties
| Property | Meaning |
|----------|---------|
| read | Can read value |
| write | Can write with response |
| write-without-response | Can write without response |
| notify | Device pushes updates |
| indicate | Device pushes with confirmation |

## ESP32 Marauder WiFi Tools

### Setup Requirement

The Marauder module communicates with the ESP32 via the Flipper UART Bridge App (dual-CDC `.fap`). Before using any `marauder_*` tool:

1. Install the UART Bridge App on the Flipper (`flipper_apps/uart_bridge/`).
2. Launch the app on the Flipper — it bridges USB CDC Channel 1 to GPIO pins 13/14.
3. Connect the ESP32 Marauder board to Flipper GPIO pins 13 (TX) and 14 (RX).

The MCP module auto-detects the CDC Channel 1 port. No manual serial configuration is needed.

### MCP Tools (marauder module — 16 tools)

| Tool | What it does |
|------|-------------|
| `marauder_scan_ap` | Scan for WiFi access points (passive) |
| `marauder_scan_sta` | Scan for WiFi client stations |
| `marauder_sniff_pmkid` | Sniff PMKID/EAPOL handshakes for offline cracking |
| `marauder_sniff_raw` | Raw 802.11 packet capture |
| `marauder_sniff_beacon` | Sniff beacon frames |
| `marauder_sniff_deauth` | Sniff deauthentication frames |
| `marauder_deauth` | Deauthentication attack against target AP/station |
| `marauder_beacon_spam` | Beacon spam (random SSIDs or named SSID list) |
| `marauder_probe_flood` | Probe request flood |
| `marauder_script` | Upload and run a Marauder script file |
| `marauder_exec` | Execute a raw Marauder serial command |
| `marauder_list_scripts` | List available Marauder scripts on SD card |
| `marauder_list_pcaps` | List captured pcap files on SD card |
| `marauder_read_log` | Read Marauder log output |
| `marauder_evil_portal` | Launch evil portal (captive portal) attack |
| `marauder_karma` | Karma attack (respond to all probe requests) |

### Raw Marauder Serial Commands (via `marauder_exec`)

| Command | What it does |
|---------|-------------|
| `scanap` | Scan WiFi access points |
| `scansta` | Scan WiFi client stations |
| `stopscan` | Stop any running scan/attack |
| `attack -t deauth` | Deauthentication attack |
| `attack -t beacon -r` | Random beacon spam |
| `attack -t beacon -l SSID1,SSID2` | Named beacon spam |
| `attack -t probe` | Probe request flood |

## Known Firmware Quirks (v1.4.3)

- `rfid` command doesn't exist — use `lfrfid` instead
- `subghz rx {freq}` blocks indefinitely — needs timeout handling
- `nfc field` returns ASCII art screen rendering, not structured data
- CLI bridge can fail to re-enter RPC after long-running commands
- Some CLI commands differ from pyFlipper documentation
