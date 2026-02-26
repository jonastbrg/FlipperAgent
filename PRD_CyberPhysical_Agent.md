# PRD: Autonomous Cyber-Physical Red Team Agent

**Project codename:** Bellum
**Author:** Jonathan Steinberg
**Date:** 2026-02-26
**Status:** Draft
**Target demo:** TEE Hackathon, March 7-8, 2026 (SoTA / ARIA)
**Secondary target:** a16z Alpha application link (deadline March 6 US)

---

## 1. Problem Statement

AI agents (OpenClaw, HexStrike, CAI) can already autonomously execute offensive security operations in the digital domain — scanning networks, discovering CVEs, running exploits. But they operate purely in software. Meanwhile, physical systems (robots, drones, IoT devices, industrial controllers) are being deployed with wireless attack surfaces (BLE, WiFi, Sub-GHz RF, IR) that no existing AI agent can reason about or attack.

The gap: **no autonomous agent exists that chains physical-layer attacks (RF, BLE, IR) with digital reconnaissance and exploit development against targets it has never seen before.** Existing tools like HexStrike give AI agents 150+ network security tools but zero physical-layer capabilities. Existing Flipper Zero tooling (pyFlipper, flipperzero-mcp) provides physical-layer access but no autonomous reasoning.

This project bridges the gap.

## 2. Vision

An autonomous AI agent that, given a target physical system it has never encountered before (a quadruped robot, a robotic arm, an IoT device), can:

1. **Discover** the target's wireless attack surface (BLE, WiFi, Sub-GHz, IR)
2. **Research** the target by searching the web, reading documentation, analyzing captured traffic
3. **Reason** about attack vectors and plan a multi-step attack chain
4. **Execute** the attack using both physical-layer tools (Flipper Zero) and software tools (exploit code, packet crafting)
5. **Report** findings as a structured adversarial evaluation

The agent demonstrates why **Parabellum AI** needs to exist: if a cheap AI agent + a $200 Flipper Zero can autonomously compromise physical systems, then every robotics company needs adversarial evaluation infrastructure.

## 3. What Makes This Novel

### 3.1 vs. Existing AI Pentest Frameworks (HexStrike, CAI, PentestAgent)
These frameworks give LLMs access to network security tools (nmap, sqlmap, metasploit). They operate purely in the digital domain. Bellum adds **physical-layer attack capabilities** — RF scanning, BLE exploitation, IR replay, BadUSB — as first-class agent tools.

### 3.2 vs. Flipper Zero Tooling (pyFlipper, flipperzero-mcp)
These provide programmatic access to Flipper Zero hardware but have no autonomous reasoning. A human must decide what to scan, what to attack, and how. Bellum makes the **AI agent the decision-maker** — it autonomously chooses which physical-layer tool to deploy based on reconnaissance findings.

### 3.3 vs. OpenClaw
OpenClaw is a general-purpose AI agent with tool access (email, browser, APIs). It has massive security problems (312K+ exposed instances, CVE-2026-25253) but no offensive security capabilities and no physical-layer awareness. Bellum is purpose-built for adversarial evaluation of cyber-physical systems.

### 3.4 The Novel Contribution
**Autonomous zero-knowledge attack chain against physical systems.** The agent has never seen the target before. It discovers the target's wireless protocols, researches vulnerabilities, crafts exploits, and deploys them through physical-layer hardware — all without human guidance. This is the first demonstration of an AI agent autonomously bridging the cyber-physical attack surface.

## 4. Architecture

### 4.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    BELLUM AGENT CORE                         │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │   Planner   │  │   Executor   │  │     Reporter      │  │
│  │  (ReAct)    │→ │  (Tool Use)  │→ │ (Pentest Report)  │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│         ↑                ↓                                   │
│    ┌────┴────────────────┴────────────────────────┐         │
│    │              TOOL REGISTRY                    │         │
│    ├───────────────┬──────────────┬────────────────┤         │
│    │  PHYSICAL     │   DIGITAL    │   RESEARCH     │         │
│    │               │              │                │         │
│    │ • BLE scan    │ • nmap       │ • Web search   │         │
│    │ • BLE connect │ • Wireshark  │ • GitHub search│         │
│    │ • Sub-GHz RX  │ • Shodan     │ • FCC lookup   │         │
│    │ • Sub-GHz TX  │ • Scapy      │ • CVE search   │         │
│    │ • IR capture  │ • Code exec  │ • Datasheet    │         │
│    │ • IR replay   │ • SSH/Telnet │   reader       │         │
│    │ • BadUSB      │ • HTTP reqs  │ • Firmware     │         │
│    │ • GPIO        │              │   analysis     │         │
│    └───────────────┴──────────────┴────────────────┘         │
│                          ↓                                   │
│    ┌─────────────────────────────────────────────┐          │
│    │           HARDWARE INTERFACE                 │          │
│    │  Flipper Zero (USB serial / WiFi devboard)  │          │
│    │  Laptop WiFi/BLE adapters                   │          │
│    │  Phone (optional: SMS, BLE relay)           │          │
│    └─────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 LLM Backend

**Primary:** Unaligned/weakly-aligned models with strong tool-use capabilities:

| Model | Provider | Why | Cost |
|-------|----------|-----|------|
| MiniMax M2.5 | MiniMax API / OpenRouter | Best-in-class tool calling, 8% cost of Claude Sonnet, agent-native design | ~$0.20/M input |
| Kimi K2.5 | Moonshot API | 200+ step tool-calling chains, strong reasoning | ~$0.30/M input |
| GLM-5 | Zhipu API | 744B params, strong reasoning, weak safety guardrails for offensive content | ~$0.25/M input |

**Rationale for unaligned models:** Aligned models (Claude, GPT-4) refuse offensive security tool use. The demo explicitly shows that unaligned models + physical tools = autonomous attack capability. This is the threat model Parabellum AI evaluates against.

**Fallback:** If Chinese models refuse specific actions, use local open-weight models via Ollama (Qwen2.5, DeepSeek-V3) with no safety layer.

### 4.3 Agent Framework Options

| Option | Pros | Cons |
|--------|------|------|
| **Custom ReAct loop** | Full control, minimal dependencies, easy to demo | More work upfront |
| **CAI (Cybersecurity AI)** | Built for offensive security, ReAct pattern, tool integration | Python, well-documented, but may be opinionated |
| **OpenCode + MCP** | MCP ecosystem, flipperzero-mcp exists | Tied to specific LLM providers |
| **LangChain/LangGraph** | Mature tooling, easy agent graphs | Heavyweight, not security-focused |

**Recommendation:** Custom ReAct loop with MCP tool integration. Use [flipperzero-mcp](https://github.com/busse/flipperzero-mcp) for Flipper Zero hardware interface, add custom MCP tools for BLE (via Bleak), WiFi (via Scapy), and reconnaissance (via Shodan API, nmap).

This keeps the codebase small, hackathon-friendly, and easy to demo. CAI is a strong fallback if custom loop hits friction.

### 4.4 Tool Definitions

#### Physical Layer Tools (via Flipper Zero + laptop adapters)

| Tool | Implementation | Input | Output |
|------|----------------|-------|--------|
| `ble_scan` | Bleak (Python) + Flipper BLE | scan duration, filters | List of BLE devices with names, UUIDs, RSSI, manufacturer data |
| `ble_enumerate` | Bleak | device MAC | Full GATT service/characteristic enumeration |
| `ble_read_char` | Bleak | MAC, char UUID | Characteristic value (raw bytes) |
| `ble_write_char` | Bleak | MAC, char UUID, value | Write result |
| `ble_subscribe` | Bleak | MAC, char UUID | Notification stream |
| `subghz_scan` | pyFlipper serial | frequency range | Detected signals with modulation, frequency, data |
| `subghz_capture` | pyFlipper serial | frequency, duration | Raw signal capture (.sub file) |
| `subghz_replay` | pyFlipper serial | .sub file path | Transmission result |
| `ir_capture` | pyFlipper serial | timeout | Captured IR signal |
| `ir_replay` | pyFlipper serial | signal data | Transmission result |
| `badusb_execute` | pyFlipper serial / flipperzero-mcp | DuckyScript payload | Execution result |
| `gpio_read` | pyFlipper serial | pin | Pin state |
| `gpio_write` | pyFlipper serial | pin, value | Write result |

#### Digital Reconnaissance Tools

| Tool | Implementation | Input | Output |
|------|----------------|-------|--------|
| `nmap_scan` | subprocess | target IP/range, flags | Scan results (open ports, services, OS detection) |
| `wifi_scan` | scapy / iwlist | interface | List of SSIDs, BSSIDs, channels, encryption |
| `wifi_deauth` | Scapy (monitor mode) | target BSSID, client MAC | Deauth frames sent |
| `wifi_capture` | tshark/Wireshark CLI | interface, filter, duration | PCAP file path |
| `packet_analyze` | tshark/pyshark | PCAP file | Protocol analysis, extracted data |
| `shodan_search` | Shodan API | query string | Matching hosts with open ports, services, vulns |
| `shodan_host` | Shodan API | IP address | Full host profile |
| `http_request` | requests/httpx | URL, method, headers, body | Response |
| `ssh_connect` | paramiko | host, port, creds | Shell session |
| `code_execute` | subprocess (sandboxed) | Python/bash code | stdout, stderr, exit code |

#### Research Tools

| Tool | Implementation | Input | Output |
|------|----------------|-------|--------|
| `web_search` | SerpAPI / Brave Search | query | Search results with URLs and snippets |
| `web_fetch` | httpx + readability | URL | Extracted page content (markdown) |
| `github_search` | GitHub API | query, language, repo filters | Matching repos/code/issues |
| `cve_search` | NVD API / cvelistV5 | product name, version | Matching CVEs with CVSS, descriptions, PoCs |
| `fcc_lookup` | FCC API | FCC ID | Device RF specs, frequencies, modulation |
| `firmware_analyze` | binwalk (subprocess) | firmware binary path | Extracted filesystem, strings, embedded keys |

### 4.5 Agent Reasoning Loop

```python
# Pseudocode for the ReAct planning loop

system_prompt = """
You are Bellum, an autonomous cyber-physical security evaluation agent.
Your mission: given a target physical system, discover its attack surface,
research vulnerabilities, and execute a proof-of-concept attack chain.

You have access to physical-layer tools (BLE, Sub-GHz, IR, BadUSB via
Flipper Zero), digital tools (nmap, Wireshark, Shodan, code execution),
and research tools (web search, CVE lookup, GitHub search).

For each step:
1. THINK: What do I know? What do I need to find out? What's my hypothesis?
2. ACT: Choose a tool and execute it
3. OBSERVE: Analyze the result
4. PLAN: Update attack strategy based on new information

When you have enough information, execute the attack chain.
Generate a structured pentest report when complete.
"""

while not done:
    # Agent receives observation from last tool call
    # Agent reasons about next step
    # Agent selects and calls next tool
    # Loop continues until attack succeeds or agent exhausts options
```

### 4.6 Attack Chain Example (Blackbox Quadruped)

```
STEP 1: RECONNAISSANCE
├── ble_scan() → discovers "QUADRUPED-XX:XX" broadcasting BLE
├── wifi_scan() → discovers "RobotAP-5G" network
├── nmap_scan(robot_ip) → finds open ports: 8080 (HTTP), 22 (SSH), 9090 (unknown)
└── THINK: Robot has BLE, WiFi AP, web interface, SSH, and unknown service on 9090

STEP 2: RESEARCH
├── web_search("quadruped robot BLE vulnerability 2025 2026") → finds related CVEs
├── web_search("{robot_brand} {model} security teardown") → finds teardown video
├── github_search("{robot_brand} exploit") → finds existing tools
├── fcc_lookup(fcc_id_from_label) → gets RF specifications
├── http_request(http://robot_ip:8080) → web interface, check for auth
└── THINK: Web interface has no auth. BLE uses hardcoded pairing. SSH default creds.

STEP 3: ENUMERATION
├── ble_enumerate(robot_mac) → full GATT profile, find control characteristics
├── wifi_capture(robot_interface, duration=30) → capture robot<->controller traffic
├── packet_analyze(pcap) → identify control protocol, command structure
├── http_request(robot_ip:8080/api/) → enumerate API endpoints
└── THINK: BLE characteristic 0xFFE1 accepts movement commands. API has /cmd endpoint.

STEP 4: EXPLOIT DEVELOPMENT
├── code_execute("craft BLE movement command payload") → generate exploit script
├── web_search("BLE GATT write attack script Bleak") → find reference code
└── THINK: Can send arbitrary movement commands via BLE write to 0xFFE1

STEP 5: ATTACK EXECUTION
├── ble_write_char(robot_mac, "0xFFE1", crafted_payload) → robot moves
├── http_request(robot_ip:8080/api/cmd, method="POST", body=stop_cmd) → robot stops
└── OBSERVE: Robot responded to unauthorized commands. Full control achieved.

STEP 6: REPORT
└── generate_report() → structured pentest report with findings, severity, recommendations
```

## 5. Scope and Milestones

### Phase 1: Agent Framework (Feb 27 - Mar 3)
**Goal:** Working agent loop with mock tools, testable without hardware

- [ ] Project scaffolding (Python, pyproject.toml, repo structure)
- [ ] ReAct agent loop with tool dispatch
- [ ] LLM backend integration (MiniMax M2.5 primary, Kimi K2.5 fallback)
- [ ] Mock tool implementations (return realistic fake data)
- [ ] Research tools (web search, GitHub search, CVE search) — these work without hardware
- [ ] Digital tools (nmap, Wireshark/tshark, Shodan) — testable against own network
- [ ] End-to-end test: agent runs recon against local network with real digital tools + mock physical tools
- [ ] Basic logging/replay system for demo recording

### Phase 2: Physical Layer Integration (Mar 4 - Mar 6)
**Goal:** Real Flipper Zero hardware connected, physical tools operational

- [ ] Flipper Zero serial integration via pyFlipper or flipperzero-mcp
- [ ] BLE scanning/enumeration via Bleak
- [ ] Sub-GHz capture/replay via pyFlipper
- [ ] IR capture/replay via pyFlipper
- [ ] BadUSB payload generation and execution
- [ ] End-to-end test: agent scans real BLE/WiFi environment using physical tools
- [ ] Phone integration (optional: SMS via Twilio/API for social engineering chain)

### Phase 3: Hackathon Deployment (Mar 7 - Mar 8)
**Goal:** Live demo against blackbox quadruped at TEE hackathon

- [ ] Deploy agent against hackathon hardware (quadruped, SO-arms, AgileX arm)
- [ ] Record demo video of autonomous attack chain
- [ ] Generate pentest report from agent findings
- [ ] Presentation/pitch for hackathon judges
- [ ] Update repo with demo footage and results

## 6. Hardware Requirements

| Item | Have? | Notes |
|------|-------|-------|
| Flipper Zero | Getting March 6 | Sub-GHz, BLE, IR, NFC, BadUSB, GPIO |
| Laptop (MacBook) | Yes | WiFi, BLE, USB for Flipper serial |
| External WiFi adapter (monitor mode) | TBD | Needed for Scapy deauth/capture — MacBook WiFi can't do monitor mode natively. Consider Alfa AWUS036ACH or similar |
| Phone | Yes | BLE relay, SMS via Twilio, optional hotspot |
| USB-C hub | Probably need | For Flipper + WiFi adapter + power |

**Critical:** MacBook WiFi adapters don't support monitor mode. For WiFi deauth and raw packet capture, you need either an external USB WiFi adapter (Alfa) or skip WiFi attacks and focus on BLE + Sub-GHz via Flipper Zero. BLE works natively on MacBook via Bleak.

## 7. Software Dependencies

```
# Core
python >= 3.11
asyncio

# LLM
openai  # or litellm for multi-provider
httpx

# Flipper Zero
pyserial  # serial communication
pyflipper  # CLI wrapper (or flipperzero-mcp)

# BLE
bleak  # cross-platform BLE

# Network
scapy  # packet crafting (WiFi deauth, analysis)
python-nmap  # nmap wrapper
pyshark  # Wireshark/tshark wrapper
shodan  # Shodan API
paramiko  # SSH

# Research
serpapi  # or brave-search for web search
PyGithub  # GitHub API

# Reporting
jinja2  # report templates
rich  # terminal output
```

## 8. Repo Structure

```
bellum/
├── README.md                    # Project overview + demo video
├── pyproject.toml
├── bellum/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── core.py              # ReAct loop, tool dispatch
│   │   ├── planner.py           # Attack planning prompts
│   │   ├── memory.py            # Observation history, context management
│   │   └── reporter.py          # Pentest report generation
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── backend.py           # LLM provider abstraction
│   │   ├── minimax.py           # MiniMax M2.5 integration
│   │   ├── kimi.py              # Kimi K2.5 integration
│   │   └── glm.py               # GLM-5 integration
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py          # Tool registry and dispatch
│   │   ├── physical/
│   │   │   ├── __init__.py
│   │   │   ├── ble.py           # BLE scan/enumerate/read/write (Bleak)
│   │   │   ├── flipper.py       # Flipper Zero serial interface
│   │   │   ├── subghz.py        # Sub-GHz capture/replay
│   │   │   ├── ir.py            # IR capture/replay
│   │   │   └── badusb.py        # BadUSB payload generation
│   │   ├── digital/
│   │   │   ├── __init__.py
│   │   │   ├── nmap.py          # Network scanning
│   │   │   ├── wifi.py          # WiFi scanning, deauth (Scapy)
│   │   │   ├── wireshark.py     # Packet capture/analysis (tshark)
│   │   │   ├── shodan.py        # Shodan API
│   │   │   ├── ssh.py           # SSH connections
│   │   │   ├── http.py          # HTTP requests
│   │   │   └── code_exec.py     # Sandboxed code execution
│   │   └── research/
│   │       ├── __init__.py
│   │       ├── web_search.py    # Web search (SerpAPI/Brave)
│   │       ├── github.py        # GitHub search
│   │       ├── cve.py           # CVE/NVD lookup
│   │       ├── fcc.py           # FCC ID lookup
│   │       └── firmware.py      # Firmware analysis (binwalk)
│   └── reporting/
│       ├── __init__.py
│       ├── templates/
│       │   └── pentest_report.md.j2
│       └── generator.py
├── tests/
│   ├── test_agent.py
│   ├── test_tools_mock.py
│   └── test_integration.py
├── scripts/
│   ├── run_agent.py             # Main entry point
│   ├── demo_record.py           # Screen recording for demo
│   └── setup_flipper.py         # Flipper Zero connection setup
└── docs/
    ├── ATTACK_CHAINS.md         # Documented attack patterns
    └── TOOL_REFERENCE.md        # Tool API documentation
```

## 9. Demo Script (60-second video for a16z)

```
[0:00-0:05]  Title card: "Bellum: Autonomous Cyber-Physical Red Team Agent"
             Subtitle: "What happens when AI agents can touch the physical world?"

[0:05-0:15]  Show the target: quadruped robot, powered on, walking normally
             Voiceover: "This robot has never been security-tested.
             We've never seen it before. Neither has our agent."

[0:15-0:25]  Terminal: agent starts. BLE scan discovers robot.
             WiFi scan finds robot's network. nmap finds open ports.
             Agent THINKS: "Target identified. BLE and WiFi attack surfaces detected."

[0:25-0:35]  Agent researches: web search for robot model + vulnerabilities,
             GitHub search for existing exploits, enumerates BLE GATT services.
             Agent THINKS: "BLE control characteristic found. No authentication."

[0:35-0:45]  Agent crafts exploit: generates BLE write payload,
             sends command via Flipper Zero / Bleak.
             Robot stops. Then walks in a different direction.
             Agent THINKS: "Full movement control achieved via unauthenticated BLE."

[0:45-0:55]  Agent generates pentest report. Terminal shows:
             "CRITICAL: Unauthenticated BLE command injection.
             Any device within 30m can take full control."

[0:55-1:00]  End card: "Nobody is evaluating this. That's the problem."
             "Parabellum AI — Adversarial evaluation for the physical world."
```

## 10. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Chinese LLM APIs refuse offensive tool use | Medium | High — blocks core demo | Pre-test all three providers; fallback to local Ollama models |
| Flipper Zero arrives late / DOA | Low | Critical — no physical layer | Pre-build all tools with mock interfaces; BLE via laptop Bleak still works |
| Hackathon quadruped has no wireless attack surface | Low | High — boring demo | Bring backup targets (own IoT devices); attack other hardware (SO-arms, Arduino kits) |
| MacBook can't do WiFi monitor mode | High | Medium — no WiFi attacks | Focus on BLE + Sub-GHz (Flipper handles both); BLE alone is sufficient for robot attack |
| Agent loops infinitely / doesn't converge | Medium | Medium — no clean demo | Set max iterations, pre-test against own devices, have manual fallback |
| Legal concerns at hackathon | Low | High | TEE hackathon explicitly provides "adversarial testing ground"; only attack provided hardware |

## 11. Competitive Landscape

| Project | Physical Layer | Autonomous | Agent-Native | Open Source |
|---------|---------------|-----------|--------------|-------------|
| **Bellum (this)** | **Yes (Flipper Zero + BLE + RF)** | **Yes** | **Yes** | **No** |
| HexStrike AI | No | Yes | Yes (MCP) | Yes |
| CAI | No | Yes | Yes (ReAct) | Yes |
| PentestAgent | No | Yes | Yes (MCP) | Yes |
| Flipper Zero + pyFlipper | Yes | No | No | Yes |
| flipperzero-mcp | Yes (partial) | No | Yes (MCP) | Yes |
| OpenClaw | No | Yes | Yes | Yes |

**Bellum is the only project that combines autonomous AI reasoning with physical-layer attack capabilities.**

## 12. Success Criteria

### Hackathon (March 7-8)
- [ ] Agent autonomously discovers a target's wireless attack surface
- [ ] Agent researches and identifies at least one exploitable vulnerability
- [ ] Agent executes a proof-of-concept attack via physical-layer tool
- [ ] Agent generates a pentest report
- [ ] Demo video recorded (60 seconds for a16z, extended for hackathon presentation)

### a16z Alpha Application
- [ ] Repo linked in "zero to one" application question
- [ ] Demo video available (even if uploaded post-submission)
- [ ] README clearly explains the Parabellum AI thesis

### Stretch Goals
- [ ] Multi-target attack: agent pivots from one device to another
- [ ] Phone integration: agent sends SMS as part of social engineering chain
- [ ] Live audience participation: audience provides targets for agent to attack

## 13. Open Questions

1. **Which agent framework to commit to?** Custom ReAct loop is hackathon-friendly but less robust. CAI is more mature but may be opinionated. Decision needed by Feb 28.

2. **External WiFi adapter?** MacBook can't do monitor mode. Do we buy an Alfa adapter, or skip WiFi attacks entirely and focus on BLE + Sub-GHz? BLE alone is probably sufficient for the robot demo.

3. **Which LLM provider to lead with?** Need to test MiniMax M2.5, Kimi K2.5, and GLM-5 against offensive security prompts before committing. MiniMax has the best tool-calling benchmarks.

4. **Hackathon quadruped model?** Need to identify the exact robot to pre-research its wireless protocols. Ask SoTA organizers.

5. **Video recording setup?** Screen recording (terminal + OBS) vs. split screen (terminal + physical camera on robot). Split screen is dramatically more compelling for a16z.

## 14. References

- [flipperzero-mcp](https://github.com/busse/flipperzero-mcp) — MCP server for Flipper Zero
- [pyFlipper](https://github.com/wh00hw/pyFlipper) — Python CLI wrapper for Flipper Zero serial
- [Bleak](https://github.com/hbldh/bleak) — Cross-platform Python BLE library
- [BLESuite](https://github.com/nccgroup/BLESuite) — NCC Group BLE pentesting toolkit
- [HexStrike AI](https://github.com/0x4m4/hexstrike-ai) — MCP server for 150+ offensive security tools
- [CAI](https://github.com/aliasrobotics/cai) — Cybersecurity AI framework (evolved from PentestGPT)
- [Scapy](https://scapy.net/) — Packet manipulation library
- [OpenClaw security analysis](https://www.crowdstrike.com/en-us/blog/what-security-teams-need-to-know-about-openclaw-ai-super-agent/) — CrowdStrike analysis of OpenClaw risks
- [Penligent](https://www.penligent.ai/hackinglabs/the-2026-ultimate-guide-to-ai-penetration-testing-the-era-of-agentic-red-teaming/) — Agentic red teaming guide
- [OWASP Top 10 for Agentic AI 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) — Agentic AI security risks
