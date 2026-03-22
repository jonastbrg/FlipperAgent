---
name: wireshark-capture
description: "Wireshark/tshark packet capture and analysis via WireMCP — BLE traffic capture on macOS, PCAP analysis, integration with FlipperAgent campaign workflow"
---

# Wireshark Capture & BLE Traffic Analysis

Capture, analyze, and interpret network and BLE traffic using Wireshark/tshark, the WireMCP MCP server, and macOS-native Bluetooth tools. This skill covers the full pipeline from raw packet capture to LLM-assisted protocol analysis.

## Part 1: WireMCP Setup

### What Is WireMCP

WireMCP is an MCP server by [0xKoda](https://github.com/0xKoda/WireMCP) that wraps Wireshark's `tshark` CLI, exposing packet capture and analysis as MCP tools. It lets LLMs perform real-time network traffic analysis, threat hunting, and protocol inspection.

**Repository:** https://github.com/0xKoda/WireMCP
**License:** MIT
**Platforms:** macOS, Linux, Windows

### Prerequisites

```bash
# 1. Install Wireshark (includes tshark)
brew install --cask wireshark

# Verify tshark is in PATH
tshark --version

# If tshark is not in PATH on macOS, it lives at:
# /Applications/Wireshark.app/Contents/MacOS/tshark
# Add to PATH or WireMCP will auto-detect this location.

# 2. Node.js v16+ required
node --version  # must be >= 16
```

### Installation

```bash
cd <project-root>
git clone https://github.com/0xKoda/WireMCP.git
cd WireMCP
npm install
```

### Test the Server

```bash
node ./WireMCP/index.js
# Server starts on stdio — it's an MCP server, not an HTTP server.
# Press Ctrl+C to stop.
```

### Configure for Claude Desktop / OpenCode

Add to your MCP client config. For Claude Desktop, edit:
`~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "wiremcp": {
      "command": "node",
      "args": ["./WireMCP/index.js"]
    }
  }
}
```

For OpenCode, add to `.opencode/config.json`:

```json
{
  "mcp": {
    "wiremcp": {
      "command": "node",
      "args": ["./WireMCP/index.js"]
    }
  }
}
```

### WireMCP Tools Reference

| Tool | Description | Use Case |
|------|-------------|----------|
| `capture_packets` | Live traffic capture, returns packet data as JSON | Real-time network monitoring, capturing traffic during BLE proxy tests |
| `get_summary_stats` | Protocol hierarchy statistics | Overview of traffic composition (TCP vs UDP vs BLE vs HTTP) |
| `get_conversations` | TCP/UDP conversation flow tracking | Identify communication endpoints and data volumes |
| `check_threats` | IP validation against URLhaus blacklist | Check if captured IPs are known malicious |
| `check_ip_threats` | Targeted threat intel lookups across multiple feeds | Deep threat intelligence on specific IPs |
| `analyze_pcap` | Post-capture PCAP file analysis in JSON format | Analyze saved captures from PacketLogger, nRF Sniffer, or tshark |
| `extract_credentials` | Scan for credentials in HTTP Basic Auth, FTP, Telnet | Credential harvesting from unencrypted protocols |

### Security Warning

WireMCP has a known command injection vulnerability (GitHub Issue #12) due to unsafe `child_process.exec` usage. Mitigations:
- Run WireMCP in a sandboxed environment or container
- Do not expose WireMCP to untrusted MCP clients
- Validate all inputs before passing to WireMCP tools
- Consider forking and patching `exec` calls to use `execFile` with argument arrays

## Part 2: Capturing BLE Traffic on macOS

macOS does not support live BLE capture through Wireshark directly. The Mac's internal Bluetooth hardware uses an undocumented mechanism not accessible via libpcap. There are three approaches, listed from simplest to most capable.

### Method A: Apple PacketLogger (Simplest, No Extra Hardware)

PacketLogger captures all Bluetooth HCI traffic to/from the Mac. It can capture BLE advertisements, connections, GATT operations, and pairing exchanges that the Mac itself participates in.

**Limitation:** Only captures traffic involving your Mac as a participant. Cannot passively sniff third-party BLE connections (e.g., WHOOP to iPhone).

#### Install PacketLogger

1. Open Xcode > Open Developer Tool > More Developer Tools
2. Download "Additional Tools for Xcode" from Apple Developer downloads
3. Mount the DMG, find PacketLogger in the `Hardware/` folder
4. Drag PacketLogger to `/Applications/`

Alternatively, download directly from:
https://developer.apple.com/download/all/?q=Additional%20Tools

#### Capture BLE Traffic from Mac

```
1. Open PacketLogger
2. Click "Clear" to start fresh
3. Start your BLE activity (e.g., connect to a device via CoreBluetooth app)
4. PacketLogger automatically captures all HCI traffic
5. Save as .pklg file: File > Save
```

#### Capture BLE Traffic from iOS Device

```
1. Install the Bluetooth Development Profile on your iPhone:
   - Go to Settings > Developer > Bluetooth Central/Peripheral Logging > Enable
   - Or download the profile from developer.apple.com/bug-reporting/profiles-and-logs
2. Connect iPhone to Mac via USB
3. In PacketLogger: File > New iOS Trace
4. Perform BLE activity on the iPhone (e.g., open WHOOP app)
5. PacketLogger captures iPhone's Bluetooth HCI traffic
6. Save as .pklg file
```

#### Open PacketLogger Files in Wireshark

```bash
# Wireshark natively reads .pklg files
open -a Wireshark capture.pklg

# Or convert to pcapng via tshark
tshark -r capture.pklg -w capture.pcapng

# Then analyze with WireMCP
# Use the analyze_pcap tool with the .pcapng file path
```

#### Useful Wireshark Display Filters for BLE

```
# All BLE ATT (Attribute Protocol) traffic
btatt

# GATT Read/Write operations
btatt.opcode == 0x12 || btatt.opcode == 0x52  # Write Request / Write Command
btatt.opcode == 0x0a || btatt.opcode == 0x0b  # Read Request / Read Response
btatt.opcode == 0x1b                           # Handle Value Notification

# Filter by BLE device address
bluetooth.addr == aa:bb:cc:dd:ee:ff

# Filter by ATT handle
btatt.handle == 0x0012

# All GATT service discovery
btatt.opcode == 0x10 || btatt.opcode == 0x11  # Read By Group Type Req/Rsp

# BLE connection events
btle.advertising_header || btle.data_header

# L2CAP for BLE
btl2cap
```

### Method B: nRF52840 USB Dongle (Passive Over-the-Air Sniffing)

This is the recommended method for capturing BLE traffic between two third-party devices (e.g., WHOOP strap talking to iPhone). The nRF52840 dongle acts as a passive radio sniffer on the 2.4 GHz BLE channels.

**Capability:** Passive capture of BLE advertisements, connection requests, and unencrypted data on active connections. Cannot decrypt encrypted GATT traffic without the LTK.

#### Hardware Required

- Nordic Semiconductor nRF52840 USB Dongle (~$10 USD)
  - Nordic PCA10059 (official)
  - Adafruit nRF52840 Dongle (alternative)
  - MakerDiary nRF52840 MDK USB Dongle (alternative)

#### Setup

```bash
# 1. Download nRF Sniffer for Bluetooth LE from Nordic
# https://www.nordicsemi.com/Products/Development-tools/nRF-Sniffer-for-Bluetooth-LE
# Unzip the download

# 2. Flash sniffer firmware to dongle
# - Hold the dongle button, plug into USB (enters bootloader / UF2 mode)
# - RGB LED turns green, mounts as UF2BOOT mass storage
# - Drag the .uf2 firmware file onto the UF2BOOT volume
# - Dongle resets automatically

# 3. Install Python dependencies
pip install pyserial

# 4. Install Wireshark extcap plugin
# Find your Wireshark Personal Extcap path:
# Wireshark > About > Folders > Personal Extcap path
# Copy all files from the nRF Sniffer's extcap/ folder into that directory

# On macOS, typically:
cp -r /path/to/nrf_sniffer_for_bluetooth_le/extcap/* \
  ~/.config/wireshark/extcap/ 2>/dev/null || \
cp -r /path/to/nrf_sniffer_for_bluetooth_le/extcap/* \
  ~/Library/Application\ Support/Wireshark/extcap/

# Make the extcap script executable
chmod +x ~/.config/wireshark/extcap/nrf_sniffer_ble.sh 2>/dev/null
chmod +x ~/Library/Application\ Support/Wireshark/extcap/nrf_sniffer_ble.sh 2>/dev/null

# 5. Restart Wireshark — "nRF Sniffer for Bluetooth LE" appears in capture interfaces
```

#### Capture Workflow

```
1. Open Wireshark
2. Select "nRF Sniffer for Bluetooth LE" as capture interface
3. Start capture — you will see BLE advertisements from all nearby devices
4. In the nRF Sniffer toolbar, select the target device by its address
5. The sniffer follows the device into connections and captures data packets
6. Save as .pcapng for analysis
```

#### Using tshark for Headless Capture

```bash
# List available interfaces (find the nRF Sniffer)
tshark -D

# Capture BLE traffic to file (replace interface number)
tshark -i nrf_sniffer_ble -w ble_capture.pcapng

# Live capture with BLE ATT filter
tshark -i nrf_sniffer_ble -Y "btatt" -T json

# This output can be piped to WireMCP's analyze_pcap tool
```

### Method C: Flipper Zero BLE Reconnaissance (Scanning Only)

The Flipper Zero can scan and enumerate BLE devices but cannot perform full packet capture of BLE connections.

**What Flipper CAN do:**
- Detect BLE advertisements (MAC, RSSI, service UUIDs, manufacturer data)
- Scan for nearby BLE devices
- Identify device types from advertising data
- Third-party apps (Wendigo) extend scanning capabilities

**What Flipper CANNOT do:**
- Capture full BLE connection traffic
- Sniff GATT read/write operations between other devices
- Perform MITM on BLE connections
- Decrypt encrypted BLE traffic

**Best use:** Initial reconnaissance to identify targets, then use nRF52840 dongle or PacketLogger for deep capture.

```
# Use Flipper for initial BLE target discovery
flipper_ble_scan(timeout=10)

# Identify the WHOOP device by name/manufacturer data
# Then switch to nRF52840 dongle for connection-level capture
```

## Part 3: Capturing WHOOP BLE Traffic Specifically

WHOOP 4.0/5.0 uses BLE to communicate with the WHOOP iOS/Android app. The traffic includes heart rate data, device commands, and data synchronization.

### Known WHOOP BLE Characteristics

From community reverse engineering (github.com/bWanShiTong/reverse-engineering-whoop):
- **Heart Rate Service (0x180D)** — standard BLE Heart Rate, readable without pairing
- **CMD_TO_STRAP** — writable characteristic for sending commands to the device
- **Custom proprietary services** — data sync, firmware update, device configuration

### Capture Strategy

#### Option 1: Mac as BLE Proxy (PacketLogger)

Write a macOS CoreBluetooth app that acts as a man-in-the-middle:
1. App connects to WHOOP as a Central
2. App advertises as a WHOOP-like Peripheral
3. Phone connects to the app instead of real WHOOP
4. App relays all GATT operations, PacketLogger captures everything

This approach is documented at:
https://www.luminis.eu/blog/bluetooth-low-energy-logging-by-placing-a-mac-in-the-middle/

#### Option 2: nRF52840 Passive Sniff

1. Flash nRF Sniffer firmware on nRF52840 dongle
2. Open Wireshark with nRF Sniffer interface
3. Wait for WHOOP advertisement, select its address
4. Open WHOOP app on phone to trigger connection
5. Capture the connection establishment and GATT traffic
6. NOTE: If the connection is encrypted (LE Secure Connections), you will only see encrypted L2CAP payloads

#### Option 3: Android HCI Snoop Log

If testing with an Android phone:
```bash
# 1. Enable Bluetooth HCI Snoop Log on Android
#    Settings > Developer Options > Enable Bluetooth HCI Snoop Log

# 2. Use the WHOOP app normally

# 3. Pull the log via adb
adb bugreport > bugreport.zip
# Extract the btsnoop_hci.log from the bugreport

# 4. Open in Wireshark
open -a Wireshark btsnoop_hci.log

# 5. Filter for WHOOP traffic
# Filter: btatt && bluetooth.addr == <whoop_mac>
```

### Decrypting Encrypted BLE Traffic

If the BLE link is encrypted (most WHOOP connections will be), you need the Long Term Key (LTK) to decrypt:

```
# On iOS: Extract LTK using ios-deploy or Frida
# On Android: Extract from /data/misc/bluedroid/bt_config.conf (requires root)

# In Wireshark: Edit > Preferences > Protocols > Bluetooth
# Add the LTK under "SMP Key" to decrypt the traffic
```

## Part 4: Analyzing Captured Data

### With WireMCP (LLM-Assisted Analysis)

Once you have a .pcap or .pcapng file:

```
# Use WireMCP's analyze_pcap tool
# The LLM receives structured JSON of all packets and can:
# - Identify protocol patterns
# - Spot anomalies in packet sequences
# - Correlate timing between requests and responses
# - Extract readable strings and data values
# - Map GATT handles to service/characteristic UUIDs
```

### With tshark (Command Line)

```bash
# Summary statistics
tshark -r capture.pcapng -z io,stat,1

# Protocol hierarchy
tshark -r capture.pcapng -z io,phs

# BLE ATT operations as JSON
tshark -r capture.pcapng -Y "btatt" -T json

# Extract all GATT write values
tshark -r capture.pcapng -Y "btatt.opcode == 0x12" -T fields -e btatt.handle -e btatt.value

# Extract all notification values
tshark -r capture.pcapng -Y "btatt.opcode == 0x1b" -T fields -e btatt.handle -e btatt.value

# Conversation list
tshark -r capture.pcapng -z conv,bluetooth
```

### With Protocol Analysis Skill

Feed extracted GATT write/notification values into the `protocol-analysis` skill:
1. Collect multiple packets from the same characteristic
2. Use `crc_detect` to identify checksums
3. Use `packet_decode` to map field boundaries
4. Use `crc_calculate` to forge valid packets

```bash
# Example: extract hex payloads from GATT notifications for analysis
tshark -r capture.pcapng -Y "btatt.opcode == 0x1b && btatt.handle == 0x0012" \
  -T fields -e btatt.value | tr ':' '' > payloads.txt

# Feed payloads.txt into protocol-analysis skill
```

## Part 5: Integration with FlipperAgent Campaign Workflow

### Campaign Phase Mapping

| Campaign Phase | Tool | Action |
|----------------|------|--------|
| 1. Scan & Discover | Flipper BLE scan | Identify target BLE devices, MAC addresses, advertised services |
| 2. Passive Recon | nRF52840 + Wireshark | Capture BLE advertisements and unencrypted traffic |
| 3. Active Enumeration | Flipper BLE connect | Connect and enumerate GATT services/characteristics |
| 4. Traffic Analysis | WireMCP analyze_pcap | LLM-assisted analysis of captured PCAP files |
| 5. Protocol RE | protocol-analysis skill | CRC detection, packet structure analysis on captured data |
| 6. Exploitation | Flipper BLE write | Write crafted payloads based on protocol analysis findings |
| 7. Monitoring | WireMCP capture_packets | Monitor network traffic during exploitation for side effects |

### Workflow Example: WHOOP Assessment

```
# Phase 1: Discovery
flipper_ble_scan(timeout=15)
# → Found: WHOOP-XXXXX at -45 dBm, services: [0x180D, custom UUIDs]

# Phase 2: Passive capture (run nRF52840 sniffer in background)
# Save capture as: campaigns/{id}/captures/whoop_passive_01.pcapng

# Phase 3: Active enumeration
flipper_ble_connect(mac="XX:XX:XX:XX:XX:XX")
flipper_ble_list_services()
# → Document all services, characteristics, properties

# Phase 4: Analyze passive capture
# WireMCP: analyze_pcap("campaigns/{id}/captures/whoop_passive_01.pcapng")
# → LLM identifies: heart rate notifications every 1s, command/response pairs

# Phase 5: Protocol analysis
# Feed captured command/response hex values to protocol-analysis skill
# → Identify CRC, field structure, command opcodes

# Phase 6: Craft and test payloads
flipper_ble_write_char(mac=..., service_uuid=..., char_uuid=..., value="0x...")

# Phase 7: Monitor for anomalies
# WireMCP: capture_packets during exploitation to check for network callbacks
```

### File Organization

```
campaigns/{campaign_id}/
├── campaign_state.json
├── progress.txt
├── captures/
│   ├── whoop_passive_01.pcapng      # nRF52840 sniffer capture
│   ├── whoop_ios_hci_01.pklg        # PacketLogger iOS trace
│   ├── whoop_mac_proxy_01.pcapng    # Mac BLE proxy capture
│   └── network_during_exploit.pcap  # WireMCP network capture
├── analysis/
│   ├── gatt_map.json                # Service/characteristic map
│   ├── protocol_fields.json         # Decoded packet structure
│   └── payloads.txt                 # Extracted hex payloads
└── findings/
    └── ble_findings.json            # Documented vulnerabilities
```

## Operational Notes

- WireMCP captures network (WiFi/Ethernet) traffic natively; BLE capture requires external tools (PacketLogger, nRF Sniffer) that produce PCAP files WireMCP can then analyze
- tshark must run with appropriate permissions for live capture; on macOS you may need to add your user to the `access_bpf` group: `sudo dseditgroup -o edit -a $(whoami) -t user access_bpf`
- PacketLogger .pklg files can be opened directly in Wireshark or converted to pcapng
- nRF52840 dongle captures are limited to one BLE channel at a time; the sniffer follows the target's channel hopping
- Encrypted BLE connections require the LTK to decrypt; without it, you see encrypted L2CAP payloads only
- WireMCP's `check_threats` and `check_ip_threats` are useful when BLE devices make network callbacks (e.g., fitness trackers phoning home over WiFi)
- All capture and analysis operations are passive/read-only and LOW risk unless actively writing to devices
