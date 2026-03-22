# FlipperAgent

MCP server + AI agent framework for autonomous penetration testing with Flipper Zero hardware. 67+ tools across BLE, WiFi, Sub-GHz, IR, NFC, RFID, and network protocols.

Free to run — works with local models (Ollama) or free cloud models (OpenCode Zen). No API costs required.

---

## What Can It Do?

Real capabilities, tested on real hardware:

- **Multi-protocol recon** — BLE scan + WiFi AP discovery + Sub-GHz capture + NFC/RFID detect + nmap, all in one campaign
- **BLE GATT exploitation** — enumerate services, identify writable characteristics, craft and send payloads (with user approval)
- **WiFi attacks via ESP32 Marauder** — deauth, beacon spam, evil portal, PMKID capture, probe flood (fully autonomous via custom UART Bridge app)
- **Sub-GHz replay** — record and retransmit 433/315/868 MHz signals
- **RFID/NFC cloning** — read, emulate, and write LF/HF tags
- **BadUSB/HID injection** — generate and execute DuckyScript payloads
- **Cross-protocol pivoting** — BLE device reveals WiFi creds → join network → nmap scan → exploit services
- **Autonomous campaigns** — agent spawns subagents per phase: recon → research → enumerate → exploit → report, with persistent state across sessions

Not magic — just tool orchestration at machine speed.

---

## How It Works

```
Agent (OpenCode / Claude Code)
  └── MCP Server (67+ tools, 17 modules)
        ├── Flipper Zero  ←USB serial→  Sub-GHz · IR · NFC · RFID · GPIO · BadUSB · Storage
        ├── ESP32 Marauder  ←UART Bridge→  WiFi scan · deauth · beacon spam · evil portal
        └── Laptop BLE (Bleak)  →  BLE scan · GATT enum · read/write characteristics
        └── Laptop network stack  →  nmap · Scapy · Shodan · credential testing
```

The agent calls MCP tools as function calls against real hardware. It does not simulate. The UART Bridge (see below) is what makes WiFi ops fully autonomous — no manual Flipper interaction needed.

**Ralph loop** (say "start ralph loop" or `/ralph-loop`):
1. Agent becomes orchestrator — spawns fresh-context subagents per phase
2. Each subagent: reads findings from disk → calls MCP tools → writes results
3. Exploit phase runs in your session for approval. State persists in `findings/` and `engagement_state.json`.

---

## UART Bridge

`flipper_apps/uart_bridge/` is a custom Flipper `.fap` app that enables **fully autonomous WiFi attacks** through the MCP module.

**How it works:**

The app switches Flipper to dual-CDC USB mode. Two serial ports appear on your computer:
- **Port 0** — Flipper CLI (unchanged, used by MCP)
- **Port 1** — ESP32 Marauder bridge (new, used by the WiFi module)

Anything sent to the second port goes over GPIO UART to the ESP32 Marauder at 115200 baud. Responses come back the same way. The MCP WiFi module talks directly to this port — no human interaction with the Flipper required.

**Setup:**

```bash
# 1. Install ufbt (Flipper build tool)
pip install ufbt

# 2. Build the app
cd flipper_apps/uart_bridge
ufbt build

# 3. Deploy to Flipper
ufbt launch
# or copy the .fap to SD card: /ext/apps/GPIO/uart_bridge.fap

# 4. Launch on Flipper: Apps → GPIO → UART Bridge
# A second serial port appears on your computer (/dev/tty.usbmodem*2 on macOS)

# 5. Set the port (or let the MCP module auto-detect)
export MARAUDER_PORT=/dev/tty.usbmodem1234562
```

The Flipper screen shows live byte counts in both directions. Press BACK to exit and restore normal USB mode.

---

## Architecture

```
OpenCode/Claude Code (AI agent)
  → MCP Server (67+ tools) → Flipper Zero (USB serial)
  → UART Bridge            → ESP32 Marauder (WiFi attacks)
  → Bleak (laptop BLE)     → Target BLE devices
  → Skills (on-demand)     → Shodan, nmap, Scapy, credential testing
  → Campaign system        → Persistent multi-session assessments
```

---

## Requirements

### Core

| Requirement | Install | Notes |
|---|---|---|
| Python 3.10+ | `brew install python@3.12` | Pre-installed on macOS |
| Flipper Zero | [shop.flipperzero.one](https://shop.flipperzero.one) | USB-C connection |
| MicroSD card | Any microSD | Formatted by Flipper |
| OpenCode or Claude Code | [opencode.ai](https://opencode.ai) or [claude-code](https://docs.anthropic.com/en/docs/claude-code) | AI agent runtime |
| jq | `brew install jq` | JSON processing |

### Python packages (installed via `pip install -e .`)

| Package | Purpose |
|---|---|
| `mcp` | MCP protocol framework |
| `pyserial` | USB serial communication |
| `protobuf` | Flipper RPC protocol |
| `bleak` | BLE scanning/enumeration from laptop |

### Hardware add-ons

| Hardware | What it enables |
|---|---|
| ESP32 Marauder dev board | WiFi attacks (deauth, beacon spam, evil portal, probe flood) via UART Bridge |
| NRF24 module | MouseJacker (wireless keyboard/mouse hijack) |
| ESP8266 (Wemos D1 Mini) | Passive WiFi surveying |

### Optional — API keys

| Key | Skill | Get it | What it enables |
|---|---|---|---|
| `SHODAN_API_KEY` | shodan-recon | [shodan.io](https://shodan.io) | Internet device search, host lookup, exploit search |

```bash
export SHODAN_API_KEY="your-key-here"
```

### Optional — CLI tools

| Tool | Skill | Install | What it enables |
|---|---|---|---|
| `nmap` | nmap-scan | `brew install nmap` | Network scanning, service detection, vuln scanning |
| `scapy` | packet-craft | `pip install scapy` | Packet crafting, ARP scan, sniffing (some need `sudo`) |
| `sshpass` | credential-test | `brew install hudochenkov/sshpass/sshpass` | SSH password testing |
| `mosquitto` | credential-test | `brew install mosquitto` | MQTT credential testing |
| `mysql` | credential-test | `brew install mysql-client` | MySQL credential testing |
| `redis-cli` | credential-test | `brew install redis` | Redis credential testing |
| `mongosh` | credential-test | `brew install mongosh` | MongoDB credential testing |
| `crccheck` | protocol-analysis | `pip install crccheck` | CRC calculation |

---

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/jonastbrg/FlipperAgent.git
cd FlipperAgent
./setup.sh                # installs deps, creates venv, adds 'flipper' alias

# 2. Connect Flipper Zero via USB (close qFlipper first)

# 3. Run
flipper                   # interactive — you + agent
# Then inside the session: "start ralph loop" or /ralph-loop
```

## How to Run

| Command | Mode | What happens |
|---------|------|--------------|
| `flipper` | Interactive (OpenCode) | You chat with the agent, tell it what to scan/attack, it calls tools. You're in the loop. |
| `flipper claude` | Interactive (Claude Code) | Same, but uses Claude Code as the runtime. |
| `./setup.sh` | Setup | Run once. Installs deps, creates venv, adds `flipper` shell alias. |

### Ralph Loop — Autonomous Pentest

Inside any interactive session, tell the agent to start the autonomous loop:

```
you: "start ralph loop" (OpenCode) or /ralph-loop (Claude Code)

agent: Reading engagement state... no prior engagement found.
       Starting recon phase. Spawning recon subagent...
       [subagent runs ble_scan, marauder_scan_ap, nmap — writes findings/recon.json]
       Recon complete: 14 BLE devices, 48 WiFi APs, 3 network hosts.
       Spawning research subagent...
       [subagent does OSINT — writes findings/research.json]
       ...
       Exploit phase — running directly for your approval:
       "I want to call ble_write_char on the smart lock. Approve? [y/n]"
```

The agent becomes an orchestrator — spawns fresh-context subagents for each phase (recon, research, enumerate, report). Each subagent reads findings from disk, calls MCP tools, writes results back. The **exploit phase runs in your session** so you can approve HIGH-risk actions. State persists in `findings/` and `engagement_state.json`, so you can resume across sessions.

---

## Models — Free by Default

**No API key required.** OpenCode ships with free models built in. Run `flipper`, press `/` to switch models.

| Model | Cost | Privacy | Notes |
|-------|------|---------|-------|
| Ollama (local) | **Free** | **Fully offline** | Nothing leaves your machine. `brew install ollama && ollama pull llama3.1:8b` |
| MiMo V2 Omni Free | **Free** | Cloud (OpenCode Zen) | Strong reasoning, no signup |
| MiniMax M2.5 Free | **Free** | Cloud (OpenCode Zen) | Good tool-use |
| Nemotron 3 Super Free | **Free** | Cloud (OpenCode Zen) | NVIDIA model |
| Grok 4.1 | Paid | Cloud (xAI) | Best tool-use for pentest reasoning |
| Claude Opus 4.6 | Paid | Cloud (Anthropic) / Claude Code | Best reasoning overall |

For **maximum privacy**, use Ollama — all inference runs locally, tool calls go directly to your Flipper over USB. No cloud, no API keys, no telemetry.

```bash
# Local setup (fully offline)
brew install ollama
ollama launch opencode        # auto-configures OpenCode + pulls a model
```

OpenCode supports [75+ providers](https://opencode.ai/docs/providers/) including Ollama, Groq, OpenRouter, DeepSeek, and more.

---

## Modules (67+ MCP Tools)

| Category | Module | Tools | Description |
|----------|--------|-------|-------------|
| Sub-GHz | subghz | 4 | Transmit, receive, decode RF signals (300–928 MHz) |
| Infrared | ir | 3 | TX/RX infrared (NEC, Samsung, RC5/6, SIRC) |
| NFC | nfc | 3 | Detect, emulate, field activation |
| RFID | rfid | 3 | Read, emulate, write 125 kHz tags |
| GPIO | gpio | 3 | Pin read/write/mode |
| LED | led | 1 | RGB LED control |
| Vibro | vibro | 1 | Motor control |
| Apps | apps | 2 | List and launch Flipper applications |
| Storage | storage | 6 | File operations (protobuf RPC) |
| BadUSB | badusb | 10 | HID injection with DuckyScript |
| BLE Recon | ble_recon | 5 | Scan, enumerate GATT, read/write (via Bleak on laptop) |
| **WiFi / Marauder** | **marauder** | **16** | **WiFi scan, deauth, beacon spam, evil portal, probe flood (via UART Bridge)** |
| Vuln Triage | vuln_triage | 4 | Submit, validate, classify findings |
| Connection | connection | 2 | Health check, reconnect |
| System Info | systeminfo | 1 | Device info |
| Audit | audit | 1 | Query tool call log |
| Music | music | 2 | Piezo speaker |

---

## Skills (15, loaded on-demand)

Skills are methodology guides the agent loads when it needs them. They live in `.opencode/skills/` as markdown files — no code, just instructions. The agent calls `skill("ble-exploitation")` and gets the full attack playbook injected into its context.

| Skill | What it teaches the agent | Requires |
|-------|--------------------------|----------|
| ble-exploitation | BLE GATT attack methodology | bleak |
| wifi-attack | WiFi recon, evil twin, deauth | ESP32 Marauder + UART Bridge |
| signal-analysis | RF protocol identification | *(none)* |
| credential-test | Default creds, password spraying | sshpass, curl |
| credential-attack | Attack methodology for auth testing | *(none)* |
| shodan-recon | Internet device intelligence | `SHODAN_API_KEY` |
| nmap-scan | Network scanning | nmap |
| packet-craft | Scapy packet operations | scapy, sudo |
| esp32-marauder | ESP32 WiFi attacks | ESP32 Marauder hardware |
| protocol-analysis | CRC reverse engineering | crccheck |
| pentest-report | Professional report writing | *(none)* |
| campaign | Sustained multi-target assessment | *(none)* |
| ralph-loop | Autonomous iteration methodology | jq |
| self-improve | Agent updates its own knowledge base | *(none)* |
| wireshark-capture | Packet capture via WireMCP | WireMCP |

**Adding your own skill:** Create a folder in `.opencode/skills/my-skill/` with a `SKILL.md` file. The agent can load it with `skill("my-skill")`. No code needed — just write the methodology in markdown.

**Adding a new MCP tool module:** Create `flipperzero-mcp/src/flipper_mcp/modules/mymodule/module.py` with a class extending `FlipperModule`. Implement `get_tools()` and `handle_tool_call()`. The registry auto-discovers it — no config needed. See any existing module for the pattern.

---

## Campaigns

Sustained, multi-session security assessments:

- **Target expansion trees** — discover new targets from compromised ones
- **Ralph loop** — say "start ralph loop" and the agent orchestrates the full pentest autonomously
- **Phase-based methodology** — recon → research → enumerate → exploit → report
- **Persistent state** — findings survive across sessions in `findings/` and `campaigns/`
- **Review gates** — HIGH-risk actions require user approval in the exploit phase

---

## Recommended Flipper Apps

Install via [lab.flipper.net](https://lab.flipper.net) (Chrome + USB):

| App | What it does |
|-----|-------------|
| MFKey | MIFARE Classic key cracking |
| ProtoView | Sub-GHz protocol decoder |
| Spectrum Analyzer | Frequency scanner |
| RFID Fuzzer | RFID brute force |

MouseJacker requires NRF24 hardware + build from source ([github.com/mothball187/flipperzero-nrf24](https://github.com/mothball187/flipperzero-nrf24)).

---

## Firmware

Compatible with stock firmware (tested on 1.4.3) and [Unleashed](https://github.com/DarkFlippers/unleashed-firmware) (adds 60+ rolling code protocols, same CLI/RPC API).

---

## Safety

- All tool calls risk-classified (LOW / MEDIUM / HIGH / BLOCKED)
- Audit logging on every invocation
- CLI input sanitization (injection prevention)
- Path validation (blocks `/int/`, `.key`, `.priv`)
- Safety gate plugin for HIGH-risk operations
- Human-in-the-loop: exploit phase always runs in your session for approval

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SHODAN_API_KEY` | *(none)* | Shodan API access |
| `MARAUDER_PORT` | *(auto-detect)* | ESP32 Marauder serial port (the second CDC port) |
| `FLIPPER_TRANSPORT` | `usb` | Transport: `usb` or `wifi` |
| `FLIPPER_WIFI_HOST` | *(none)* | Flipper WiFi dev board IP |
| `FLIPPER_AUDIT_LOG` | *(none)* | File path for audit JSONL output |
| `FLIPPER_MCP_ALLOW_STUB_MODE` | `false` | Run without hardware (dev/testing) |
| `HITL` | `false` | Human-in-the-loop gate for exploit phase |

---

## Based On

- [flipperzero-mcp](https://github.com/busse/flipperzero-mcp) — MCP server foundation (MIT)
- [Bleak](https://github.com/hbldh/bleak) — BLE scanning/enumeration (MIT)
- [OpenCode](https://github.com/sst/opencode) — AI agent runtime
- [crcbeagle](https://github.com/colinoflynn/crcbeagle) — CRC reverse engineering
- [ARTEMIS](https://arxiv.org/abs/2512.09882) — Autonomous red-teaming architecture reference
- [Ralph](https://github.com/snarktank/ralph) — Autonomous loop pattern

---

## Legal

**For authorized security research only.** Only test devices you own or have explicit written permission to assess. The operator is responsible for compliance with all applicable laws including CFAA (US), Computer Misuse Act (UK), and equivalent statutes in your jurisdiction.

Transmitting RF signals, deauthing WiFi networks, and cloning access credentials may be illegal without explicit authorization. The authors accept no liability for misuse.
