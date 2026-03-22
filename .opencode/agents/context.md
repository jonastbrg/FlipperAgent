---
description: Project context and knowledge base for FlipperAgent — architecture, prior findings, ecosystem intel
mode: subagent
hidden: true
permission:
  edit: deny
  bash: deny
---

# FlipperAgent Context

## Project Structure

```
FlipperAgent/
├── AGENTS.md                      — project rules (OpenCode auto-loads)
├── README.md                      — public documentation
├── opencode.jsonc                 — MCP + model config
├── flipper                        — launch interactive session (OpenCode or Claude Code)
├── .opencode/
│   ├── agents/                    — AI agent definitions
│   │   ├── flipper-agent.md       — PRIMARY agent (300+ lines, the soul)
│   │   ├── tool-reference.md      — complete CLI/tool reference
│   │   ├── context.md             — THIS FILE (knowledge base)
│   │   ├── recon.md               — recon phase subagent
│   │   ├── research.md            — research phase subagent
│   │   ├── enumerate.md           — enumeration phase subagent
│   │   ├── exploit.md             — exploitation phase subagent
│   │   └── report.md              — reporting phase subagent
│   ├── skills/                    — 15 on-demand methodology guides
│   └── plugins/                   — safety gate + audit logger
├── scripts/                       — wrapper scripts for Claude Code usage
├── flipper_apps/
│   └── uart_bridge/               — dual-CDC .fap (UART Bridge App)
├── flipperzero-mcp/               — MCP server (17 modules, 67 tools)
│   └── src/flipper_mcp/
│       ├── core/                  — CLI bridge, risk, audit, transport
│       └── modules/               — tool modules (incl. marauder)
├── findings/                      — gitignored, local scan results
└── campaigns/                     — gitignored, engagement state
```

## Architecture

```
User → ./run.sh (sets OPENCODE_DISABLE_CLAUDE_CODE=1)
  → OpenCode (loads AGENTS.md + .opencode/agents/flipper-agent.md)
    → Model (xai/grok-4-1 or configured model)
      → MCP Server (67 tools, 17 modules via stdio)
        → CLI Bridge (StopSession → CLI → RPC)
          → Flipper Zero (USB @ 230400 baud, CDC Channel 0)
        → UART Bridge App (CDC Channel 1 → GPIO pins 13/14)
          → ESP32 Marauder → WiFi radio
      → Bleak (MCP Module → Bleak → Laptop BLE adapter)
      → Skills (loaded on demand for methodology)
      → Bash (for wrapper scripts, nmap, scapy, etc.)
```

## Three Radio Paths

1. **Flipper Zero radio** (via USB serial CLI):
   - Sub-GHz 300-928 MHz (CC1101 chip)
   - Infrared TX/RX
   - NFC 13.56 MHz
   - RFID 125 kHz
   - BadUSB (USB HID)

2. **Laptop Bluetooth** (via Bleak Python library):
   - BLE scanning (passive, advertisement capture)
   - GATT enumeration (connect, map services/characteristics)
   - BLE read/write (interact with target devices)
   - This is SEPARATE from the Flipper — uses the laptop's own BT adapter
   - Full path: MCP Module → Bleak → Laptop BLE adapter

3. **ESP32 Marauder** (via UART Bridge App on Flipper):
   - WiFi AP/station scanning, PMKID sniffing, deauth, beacon spam, probe flood
   - Evil portal, karma attack, raw packet capture, scripted command execution
   - Full path: MCP Module → pyserial → USB CDC Channel 1 → Flipper UART Bridge App → GPIO pins 13/14 → ESP32 Marauder → WiFi radio
   - Requires: UART Bridge App running on Flipper + ESP32 Marauder on pins 13/14

## Firmware Compatibility

Tested on stock firmware 1.4.3. Also compatible with:
- **Unleashed** — adds 60+ rolling code protocols, no regional TX limits
- **Momentum** — BLE spam, FindMy, extended SubGHz

Same CLI/RPC interface across all firmwares. Our MCP server works unchanged.

## Known Issues

- `rfid` CLI command doesn't exist on FW 1.4.3 — use `lfrfid`
- `subghz rx` blocks indefinitely — needs timeout + Ctrl+C
- NFC field returns ASCII art, not structured data
- CLI bridge can fail to re-enter RPC after long-running commands
- Serial port exclusive — close qFlipper before connecting
- Multiple scripts hitting serial simultaneously = stuck vibro/LED

## Recommended Flipper Apps

Install via lab.flipper.net (Chrome + USB):
- MFKey — MIFARE Classic key cracking
- ProtoView — Sub-GHz protocol decoder
- Spectrum Analyzer — frequency scanner
- RFID Fuzzer — RFID brute force
