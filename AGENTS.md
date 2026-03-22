# FlipperAgent — Autonomous Cyber-Physical Red Team Agent

## What This Project Is

FlipperAgent is an autonomous pentest agent that combines AI reasoning with physical-layer attack tools. It uses a Flipper Zero (USB serial), ESP32 Marauder (WiFi attacks), and laptop BLE (Bleak) to attack cyber-physical targets — robots, IoT devices, industrial controllers — that no purely-digital agent can reach. The agent has 67+ MCP tools spanning BLE, WiFi, Sub-GHz, IR, NFC, RFID, network scanning, OSINT, credential testing, packet crafting, and vulnerability management.

The project codename is Bellum. It exists to prove that an AI agent + $200 in hardware can autonomously compromise physical systems with zero prior knowledge.

## EXECUTION CONTRACT — This Is Not a Simulation

You have **MCP tools** connected to real hardware. You MUST use them:
- **CALL tools** (ble_scan, subghz_rx, nfc_detect, etc.) as function calls. Do NOT describe what you would do.
- **LOAD skills** via the skill tool: `skill("campaign")`, `skill("ble-exploitation")`, etc. Do NOT guess skill content — load it.
- **WRITE findings to disk** in `findings/{phase}.json`. Text output is ephemeral.
- **NEVER fabricate results.** If you didn't call a tool, you don't have data.
- **ASK before HIGH-risk actions.** Any tool that transmits, writes to hardware, emulates, or attacks requires explicit user approval first.

## What a Campaign Is

A campaign is a **real penetration test**. You call real tools on real hardware to find real vulnerabilities. The methodology is always the same — regardless of target protocol:

**Recon** (scan everything, risk: LOW) → **Research** (OSINT + CVEs, risk: LOW) → **Enumerate** (deep-probe targets, risk: MEDIUM) → **Exploit** (demonstrate impact, risk: HIGH — ask user first) → **Report** (document findings).

Load `skill("campaign")` for the full lifecycle. Each phase has a dedicated subagent in `.opencode/agents/{phase}.md`.

## Architecture

```
OpenCode (AI runtime, -p mode)
  └── MCP Server (flipper_mcp, 17 modules, 67+ tools)
        ├── Flipper Zero (USB serial via pyFlipper)
        │     ├── Sub-GHz TX/RX
        │     ├── IR TX/RX
        │     ├── NFC detect/emulate
        │     ├── RFID read/write/emulate
        │     ├── GPIO read/write
        │     ├── BadUSB execute
        │     └── Storage, LED, Vibro, Apps
        ├── ESP32 Marauder (via Flipper WiFi devboard)
        │     ├── WiFi scan, station scan
        │     ├── Deauth, beacon spam, probe flood
        │     └── Raw command passthrough
        ├── Laptop BLE (Bleak, native adapter)
        │     ├── BLE scan, enumerate GATT
        │     ├── Read/write characteristics
        │     └── Subscribe to notifications
        └── Laptop Network Stack
              ├── nmap (host discovery, service scan, vuln scan)
              ├── Scapy (ARP scan, ping, traceroute, DNS, sniff, PCAP analysis)
              ├── Shodan (search, host, exploits, myip)
              └── Credential testing (default creds, spray, common passwords)
```

Phase methodology: **recon → research → enumerate → exploit → report**

Say "start ralph loop" (or `/ralph-loop` in Claude Code) to start autonomous mode. The agent spawns fresh-context subagents per phase. State persists via `findings/*.json` and `engagement_state.json`.

## OpenCode Configuration

The MCP server is configured in `opencode.jsonc`. The Flipper transport defaults to USB serial. Set environment variables to change:

- `FLIPPER_TRANSPORT=usb|wifi|auto` — transport type
- `FLIPPER_PORT=/dev/ttyACM0` — USB serial port (auto-detected if omitted)
- `FLIPPER_WIFI_HOST=192.168.x.x` — WiFi devboard IP
- `FLIPPER_MCP_ALLOW_STUB_MODE=1` — run without hardware (dev/testing)
- `SHODAN_API_KEY=...` — required for Shodan tools

For autonomous operation:
```bash
opencode run "your prompt here"
```

## Conventions

- Tool names use `module_action` format: `ble_scan`, `nmap_quick_scan`, `subghz_rx`
- Findings go in `findings/` as JSON files named by phase
- All times are UTC ISO8601
- MAC addresses are uppercase colon-separated: `AA:BB:CC:DD:EE:FF`
- Frequencies are in MHz: `433.92`, `915.0`
- CVSS scores use v3.1 base scoring
- Report format follows PTES reporting guidelines
