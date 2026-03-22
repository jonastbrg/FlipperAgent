# FlipperAgent Architecture

## Overview

FlipperAgent is an autonomous cyber-physical red team agent that pairs an AI reasoning engine (OpenCode or Claude Code) with physical-layer attack hardware (Flipper Zero, laptop Bluetooth, optional ESP32 Marauder) through a 67-tool MCP server. The agent executes a five-phase pentest pipeline -- recon, research, enumerate, exploit, report -- where each phase runs as an independent AI context window with persistent filesystem-based memory. A risk classification engine gates every tool call, an audit logger records every action, and CLI input sanitization prevents injection into the Flipper's serial interface. The result is an agent that can autonomously discover, research, and exploit wireless devices across BLE, Sub-GHz, WiFi, IR, NFC, and RFID with no prior knowledge of the target environment.

## Architecture Layers

```
+---------------------------------------------+
|         AI AGENT (OpenCode / Claude Code)    |
|  Phase agents: recon, research, enumerate,   |
|  exploit, report. Skills loaded on-demand.   |
+---------------------------------------------+
|         MCP SERVER (67 tools, 17 modules)    |
|  +-- CLI Bridge (StopSession -> CLI -> RPC)  |
|  +-- Risk Engine (LOW/MEDIUM/HIGH/BLOCKED)   |
|  +-- Audit Logger (ring buffer + JSONL)      |
|  +-- Input Sanitizer (injection prevention)  |
|  +-- Path Validator (/int/, .key, .priv)     |
|  +-- Session Manager (engagement state)      |
|  +-- Campaign Manager (multi-target trees)   |
|  +-- Transport (USB serial @ 230400 baud)    |
+---------------------------------------------+
|         HARDWARE                             |
|  +-- Flipper Zero (SubGHz, IR, NFC, RFID,   |
|  |   BadUSB, GPIO, Storage, Apps)            |
|  +-- Laptop BLE (Bleak scanner/enumerator)   |
|  +-- ESP32 Marauder (WiFi attacks, optional) |
+---------------------------------------------+
|         FILESYSTEM (shared memory)           |
|  +-- findings/*.json (per-phase results)     |
|  +-- engagement_state.json (session state)   |
|  +-- progress.txt (append-only agent notes)  |
|  +-- campaigns/*/campaign_state.json         |
+---------------------------------------------+
```

## Component Details

### AI Agent Layer

The AI agent runs inside OpenCode (`opencode -p`) or Claude Code. It has no direct hardware access -- all interaction goes through MCP tool calls. Five phase-specific agents live in `.opencode/agents/` and teach the model what to do in each pentest phase. Fifteen skills in `.opencode/skills/` provide on-demand methodology guides (BLE exploitation, WiFi attacks, signal analysis, credential testing, etc.).

Two OpenCode plugins provide runtime guardrails:

- **safety-gate.ts** -- logs a `[SAFETY]` warning to stderr whenever a HIGH-risk tool is invoked.
- **engagement-logger.ts** -- appends every tool call to `findings/tool_calls.jsonl` for post-engagement analysis.

### MCP Server Layer

The MCP server (`flipper_mcp`) is a Python process that speaks the Model Context Protocol over stdio. It is structured as:

**FlipperMCPServer** (`core/server.py`) -- the main server. Registers MCP handlers (`list_tools`, `call_tool`), manages the Flipper client lifecycle, and handles automatic reconnection when the transport drops mid-session.

**ModuleRegistry** (`core/registry.py`) -- discovers and loads tool modules from `modules/`. Each module is a self-contained Python package that registers its tools and handles its own CLI/RPC commands. The 17 modules are: subghz, ir, nfc, rfid, gpio, led, vibro, apps, storage, badusb, ble_recon, vuln_triage, connection, systeminfo, audit, music, marauder.

**CLIBridge** (`core/cli_bridge.py`) -- the most critical infrastructure component. The Flipper's USB CDC port operates in two mutually exclusive modes: CLI (text commands) and RPC (protobuf framing). Most hardware operations (GPIO, LED, SubGHz, IR) require CLI mode, while storage and device info require RPC mode. CLIBridge manages the transition:

1. Send protobuf `StopSession` to exit RPC mode
2. Fall back to Ctrl-C + CR if `StopSession` fails
3. Drain residual bytes, wait for `>:` CLI prompt
4. Send the CLI command, read until next prompt
5. Send `start_rpc_session\r` to re-enter RPC mode
6. Verify with a protobuf ping (3 retries)

All of this happens under an async lock to prevent concurrent access.

**Risk Engine** (`core/risk.py`) -- static lookup table that classifies every tool into LOW, MEDIUM, HIGH, or BLOCKED. Classification takes less than 1ms. Unknown tools default to MEDIUM. The engine also validates Flipper file paths, blocking traversal (`..`), protected prefixes (`/int/`), and sensitive suffixes (`.key`, `.priv`, `.secret`). All paths must be on the SD card (`/ext/`).

**Audit Logger** (`core/audit.py`) -- thread-safe logger that maintains an in-memory ring buffer (1000 entries) and optionally writes to a JSONL file (`FLIPPER_AUDIT_LOG` env var). Every tool call is logged with: timestamp, session ID, tool name, sanitized arguments, risk level, result summary (truncated to 200 chars), duration, and success/failure.

**Input Sanitizer** (`core/sanitize.py`) -- strips shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `()`, `{}`, `[]`, `\`, `<>`, `!`, `#`) from CLI commands before they reach the Flipper. Enforces a 512-byte maximum command length (Flipper buffer limit). Also sanitizes arguments for audit logging, redacting any field whose key contains `key`, `token`, `secret`, or `password`.

**Session Manager** (`core/session.py`) -- persists engagement state (current phase, discovered targets, vulnerabilities, credentials, attack chains, agent notes) to `findings/engagement_state.json`. Enables resumption after crashes or context window exhaustion.

**Campaign Manager** (`core/campaign.py`) -- manages sustained, multi-session assessments. Tracks a hierarchy of Campaign -> Targets -> Attack Vectors -> Findings. Supports target expansion trees (pivoting from one compromised target to discover others), priority-based target selection, and a review queue for HIGH-risk actions.

**Transport Layer** (`core/transport/`) -- abstracted transport with USB, WiFi, and Bluetooth backends. USB is the primary transport (pyserial at 230400 baud with auto-detection fallback to 115200/460800/921600). WiFi transport connects to the Flipper WiFi dev board via TCP. Auto-detection tries USB first, falls back to WiFi if `FLIPPER_WIFI_HOST` is set.

**UART Bridge App** (`flipper_apps/uart_bridge/`) -- a dual-CDC Flipper application (`.fap`) that exposes a second USB CDC channel (Channel 1) for pass-through UART communication. When the UART Bridge App is running on the Flipper, the MCP server can reach the ESP32 Marauder through the following chain: MCP Module → pyserial → USB CDC Channel 1 → Flipper UART Bridge App → GPIO pins 13/14 → ESP32 Marauder → WiFi radio. This chain is independent of the main CLI/RPC channel (Channel 0), so Marauder commands do not interrupt Flipper operations.

**FlipperClient** (`core/flipper_client.py`) -- high-level client that wraps transport + protobuf RPC + CLI bridge. Provides `connect()`, `disconnect()`, `get_device_info()`, and exposes the CLI bridge and RPC interface to modules.

### Hardware Layer

**Flipper Zero** -- connected via USB-C. Runs stock firmware (tested on 1.4.3) or Unleashed firmware. Provides SubGHz TX/RX (300-928 MHz), IR TX/RX (NEC, Samsung, RC5/6, SIRC), NFC detect/emulate, RFID read/write/emulate (125 kHz), BadUSB (HID injection via DuckyScript), GPIO read/write, and SD card storage.

**Laptop BLE** -- uses the Bleak Python library to scan, enumerate GATT services/characteristics, read/write characteristics, and subscribe to notifications. This runs on the laptop's Bluetooth adapter, not on the Flipper. The full path for BLE operations is: MCP Module → Bleak → Laptop BLE adapter. Tested against WHOOP 5.0 (34 devices discovered, GATT enumeration, HR streaming).

**ESP32 Marauder** -- optional WiFi attack board connected to the Flipper's GPIO UART pins (pins 13/14). Provides WiFi AP scanning, station scanning, PMKID/EAPOL sniffing, raw packet capture, beacon sniffing, deauth sniffing, deauthentication attacks, beacon spam, probe flooding, evil portal, karma attacks, and scripted command execution. Communication reaches the Marauder through the UART Bridge App: MCP Module → pyserial → USB CDC Channel 1 → Flipper UART Bridge App → GPIO pins 13/14 → ESP32 Marauder. Requires the UART Bridge App running on the Flipper and the ESP32 Marauder board connected to pins 13/14.

### Filesystem Layer

The AI agent and the orchestrator share state through the filesystem:

| File | Purpose |
|------|---------|
| `findings/recon.json` | Discovered targets from reconnaissance |
| `findings/research.json` | Intelligence gathered per target |
| `findings/enumerate.json` | Deep enumeration results |
| `findings/exploit.json` | Successful attacks and evidence |
| `findings/report.json` | Final structured report |
| `engagement_state.json` | Current phase, targets, vulns, attack chains |
| `progress.txt` | Append-only agent notes and learnings |
| `campaigns/*/campaign_state.json` | Multi-session campaign state |
| `findings/tool_calls.jsonl` | All MCP tool calls (engagement-logger plugin) |

## Phase Flow

```
    +-----------+     +-----------+     +-------------+     +-----------+     +--------+
    |   RECON   | --> | RESEARCH  | --> |  ENUMERATE  | --> |  EXPLOIT  | --> | REPORT |
    |           |     |           |     |             |     |           |     |        |
    | BLE scan  |     | Shodan    |     | GATT enum   |     | BLE write |     | vuln   |
    | SubGHz RX |     | CVE lookup|     | nmap vuln   |     | SubGHz TX |     | list   |
    | WiFi scan |     | web search|     | cred check  |     | cred spray|     | report |
    | nmap disc |     | protocol  |     | protocol    |     | BadUSB    |     | gen    |
    | NFC/RFID  |     | research  |     | analysis    |     | IR TX     |     |        |
    +-----------+     +-----------+     +-------------+     +-----------+     +--------+
         |                 |                  |                  |                |
         v                 v                  v                  v                v
    findings/         findings/          findings/          findings/        findings/
    recon.json        research.json      enumerate.json     exploit.json     report.json
```

Each phase runs as an independent AI context window via `opencode -p`. This prevents context window exhaustion during multi-hour engagements. The orchestrator (ralph-loop skill) drives the pipeline, injecting previous findings into each new context.

## Tool Call Flow

```
1. AI Decision
   Agent decides to call a tool (e.g., ble_scan)
                |
                v
2. OpenCode Plugin Layer
   safety-gate.ts logs HIGH-risk warnings
   engagement-logger.ts records the call
                |
                v
3. MCP Protocol
   JSON-RPC over stdio to the MCP server
                |
                v
4. FlipperMCPServer.call_tool()
   Checks Flipper connection status
   Auto-reconnects if transport is down
                |
                v
5. ModuleRegistry.route_tool_call()
   Finds the module that owns this tool
   Module classifies risk via risk.py
   Module logs via audit.py
                |
                v
6. Module Execution
   +-- BLE tools: Bleak library (laptop BT adapter)
   +-- Network tools: subprocess (nmap, scapy)
   +-- Flipper CLI tools: CLIBridge.run_cli()
   +-- Flipper RPC tools: ProtobufRPC directly
                |
                v
7. CLIBridge (for CLI tools)
   Sanitize input (sanitize.py)
   Exit RPC mode (StopSession / Ctrl-C fallback)
   Send CLI command, read until prompt
   Re-enter RPC mode (start_rpc_session + ping verify)
                |
                v
8. Hardware Response
   Flipper executes command, returns result
   Transport delivers bytes back up the chain
                |
                v
9. Response to AI
   Module formats result as TextContent
   MCP server returns via JSON-RPC
   AI processes and decides next action
```

## Risk Classification

Every tool call passes through the risk classification engine before execution.

```
Tool Call Received
        |
        v
+------------------+
| classify_tool()  |   Static lookup in TOOL_RISK_MAP
+--------+---------+   Unknown tools -> MEDIUM
         |
    +----+----+----+----+
    |         |         |         |
    v         v         v         v
+------+  +--------+  +------+  +---------+
| LOW  |  | MEDIUM |  | HIGH |  | BLOCKED |
| (27) |  |  (16)  |  |  (8) |  |         |
+--+---+  +---+----+  +--+---+  +----+----+
   |          |           |           |
   v          v           v           v
Execute    Execute     Execute     Reject
silently   (logged)    (logged +   with error
                       safety-gate  message
                       warning)
```

**LOW (27 tools):** Read-only operations, no RF emission, no state change. Examples: `ble_scan`, `subghz_rx`, `nfc_detect`, `storage_list`, `audit_query`.

**MEDIUM (16 tools):** State changes, limited-range output, enumeration that touches targets. Examples: `ir_tx`, `gpio_set`, `ble_enumerate`, `storage_write`, `badusb_generate`.

**HIGH (8 tools):** RF transmission, tag emulation/writing, HID injection, credential attacks. Examples: `subghz_tx`, `ble_write_char`, `rfid_write`, `badusb_execute`.

**BLOCKED:** Path-based blocking for protected Flipper filesystem areas. Paths containing `/int/` (internal flash), or ending in `.key`, `.priv`, `.secret` are rejected.

## Campaign System

Campaigns extend single-session engagements into sustained, multi-session assessments.

### Hierarchy

```
Campaign
  +-- Scope (description + allowed targets + exclusions)
  +-- Targets (discovered devices/services)
  |     +-- Target 1
  |     |     +-- Attack Vector A (planned/in_progress/succeeded/failed)
  |     |     +-- Attack Vector B
  |     |     +-- Children (targets discovered FROM this target)
  |     |           +-- Target 1a (expansion)
  |     +-- Target 2
  |           +-- Attack Vector C
  +-- Review Queue (HIGH-risk actions pending approval)
  +-- Decisions (timestamped rationale log)
  +-- Iteration Counter (max 50 by default)
```

### Target Expansion Tree

When exploiting one target reveals new targets (e.g., compromising a WiFi AP exposes internal network hosts), the campaign manager links them in a parent-child tree. `get_expansion_tree()` returns this as a nested dictionary for visualization. `get_next_target()` returns the highest-priority target that still needs work.

### Convergence

The Ralph loop (ralph-loop skill) drives campaigns iteratively. Each iteration is one `opencode -p` invocation. The campaign converges when:

- All targets are in terminal states (compromised or abandoned)
- The maximum iteration count is reached
- No new targets or findings are produced across consecutive iterations

## Security Architecture

### Scope Enforcement

The agent must only attack targets within the defined engagement scope. Scope is declared at campaign creation (`scope_description`, `scope_targets`, `out_of_scope`) and injected into every phase prompt. The `SCOPE` environment variable in ralph-loop skill is the primary mechanism.

### Audit Trail

Two independent audit systems capture every action:

1. **Server-side audit** (`core/audit.py`) -- ring buffer + optional JSONL file. Captures tool name, sanitized arguments, risk level, result summary, duration, and success/failure for every tool call.
2. **Plugin-side audit** (`engagement-logger.ts`) -- appends to `findings/tool_calls.jsonl` at the OpenCode plugin level, capturing tool calls even if the MCP server crashes.

### Input Sanitization

CLI commands sent to the Flipper pass through `sanitize_cli_input()` which strips shell metacharacters (`; & | \` $ () {} [] \ <> ! #`) and enforces a 512-byte length limit. This prevents command injection through the serial interface.

Audit log entries pass through `sanitize_args_for_log()` which redacts fields containing `key`, `token`, `secret`, or `password` and truncates long values to 200 characters.

### Path Validation

All Flipper filesystem operations go through `validate_flipper_path()` which enforces:

- No path traversal (`..` is rejected)
- No access to internal flash (`/int/` prefix or bare `/int` is blocked)
- No access to key/credential files (`.key`, `.priv`, `.secret` suffixes are blocked)
- All paths must be on the SD card (`/ext/` prefix required)

### Transport Security

The USB serial connection is local-only (no network exposure). The auto-reconnect logic in `FlipperMCPServer.call_tool()` detects disconnection patterns ("not connected", "broken pipe", "serialexception") and attempts one reconnect before returning an error. A port lock prevents concurrent serial access.

### Human-in-the-Loop

Setting `HITL=true` in ralph-loop skill enables a human approval gate before the exploit phase. The safety-gate plugin provides runtime HIGH-risk warnings. The campaign review queue (`queue_for_review()`) supports external approval workflows for HIGH-risk actions.

## File Structure

```
FlipperAgent/
+-- README.md                    Project documentation
+-- LICENSE                      MIT
+-- ralph-loop skill                     Autonomous loop (ralph pattern)
+-- run.sh                       Launch OpenCode (clean, no bleed)
+-- opencode.jsonc               MCP server configuration
|
+-- docs/
|   +-- architecture.md          This document
|   +-- system_prompt.md         AI system prompt
|   +-- AGENTS.md                Complete tool inventory + methodology
|   +-- CONTRIBUTING.md          Contribution guide
|   +-- SECURITY.md              Security policy
|   +-- PROJECT_STATUS.md        Full state machine diagram
|
+-- .opencode/
|   +-- agents/                  5 phase-specific AI agents
|   +-- skills/                  14 on-demand methodology skills
|   +-- plugins/                 safety-gate.ts, engagement-logger.ts
|
+-- flipperzero-mcp/             MCP server (Python)
|   +-- src/flipper_mcp/
|   |   +-- core/                Server, registry, transport, CLI bridge,
|   |   |                        risk, audit, sanitize, session, campaign
|   |   +-- modules/             17 tool modules (subghz, ir, nfc, rfid,
|   |                            gpio, led, vibro, apps, storage, badusb,
|   |                            ble_recon, vuln_triage, connection,
|   |                            systeminfo, audit, music, marauder)
|   +-- tests/                   Unit + integration tests
|
+-- flipper_apps/
|   +-- uart_bridge/             Dual-CDC .fap app (UART Bridge)
|                                Routes USB CDC Channel 1 → GPIO pins 13/14
|
+-- findings/                    Per-engagement results (gitignored)
+-- campaigns/                   Multi-session campaign state (gitignored)
```
