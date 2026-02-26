# Bellum Agent State Machine

**Version:** 1.0
**Date:** 2026-02-26
**Context:** OpenCode runtime — states are enforced via system prompts, Skills, and plugin hooks

---

## Overview

Bellum operates as a **finite state machine with conditional transitions**. The agent progresses through attack phases, with each phase producing structured output that feeds the next. Recovery paths handle tool failures, dead-end vectors, and hardware disconnections.

```
                              ┌─────────────┐
                              │    IDLE      │
                              │  (waiting)   │
                              └──────┬───────┘
                                     │ user provides target spec
                                     ▼
                              ┌─────────────┐
                              │   TARGET     │
                              │  ACQUISITION │
                              └──────┬───────┘
                                     │ target validated
                                     ▼
                         ┌──────────────────────┐
                    ┌───►│    RECONNAISSANCE     │◄──────────────┐
                    │    │  (discover surfaces)  │               │
                    │    └──────────┬────────────┘               │
                    │               │ surfaces found             │
                    │               ▼                            │
                    │    ┌──────────────────────┐               │
                    │    │      RESEARCH         │               │
                    │    │ (enrich w/ OSINT)     │               │
                    │    └──────────┬────────────┘               │
                    │               │ vulns/intel gathered       │
                    │               ▼                            │
                    │    ┌──────────────────────┐               │
                    │    │    ENUMERATION        │               │
                    │    │ (deep-dive surfaces)  │               │
                    │    └──────────┬────────────┘               │
                    │               │ attack vectors ranked      │
                    │               ▼                            │
                    │    ┌──────────────────────┐               │
                    │    │   EXPLOITATION        │               │
                    │    │ (craft + execute)     │               │
                    │    └───┬──────────┬────────┘               │
                    │        │          │                        │
                    │   success    failure                       │
                    │        │          │                        │
                    │        │          ▼                        │
                    │        │  ┌──────────────┐    vectors     │
                    │        │  │    PIVOT      │───remaining───►│
                    │        │  │ (next vector) │               │
                    │        │  └──────┬────────┘
                    │        │         │ no vectors left
                    │        │         ▼
                    │        │  ┌──────────────┐
                    │        └─►│   REPORTING   │
                    │           │ (gen report)  │
                    │           └──────┬────────┘
                    │                  │
                    │                  ▼
                    │           ┌──────────────┐
                    │           │   COMPLETE    │
                    │           └──────────────┘
                    │
                    │  ┌──────────────┐
                    └──│   RECOVERY    │ (hardware disconnect,
                       │              │  context overflow,
                       └──────────────┘  agent stuck)
```

---

## States

### S0: IDLE

**Description:** Agent is loaded, waiting for a target assignment.
**Entry conditions:** Agent startup, or previous engagement completed.
**Allowed tools:** None.
**Exit:** User provides target specification → **TARGET_ACQUISITION**

```
State: IDLE
┌──────────────────────────────────┐
│ Variables:                       │
│   engagement_id: null            │
│   target_spec: null              │
│ Actions:                         │
│   - Display ready prompt         │
│   - List available hardware      │
│ Transitions:                     │
│   → TARGET_ACQUISITION           │
│     guard: target_spec provided  │
└──────────────────────────────────┘
```

---

### S1: TARGET_ACQUISITION

**Description:** Parse and validate the target specification. Confirm hardware is connected. Establish engagement scope.

**Entry data:** Raw target spec from user (could be "that robot over there", an IP range, a device name, or "scan everything nearby").

**Actions:**
1. Parse target spec into structured form: `{ type, identifiers, scope, constraints }`
2. Verify hardware connectivity (Flipper Zero serial, BLE adapter, WiFi adapter)
3. Log hardware inventory: what's available, what's missing
4. Set engagement scope (authorized targets only)
5. Initialize checkpoint file

**State variables set:**
```json
{
  "engagement_id": "bellum-20260308-001",
  "target": {
    "description": "Quadruped robot on hackathon table 3",
    "known_identifiers": [],
    "scope": "BLE/WiFi/Sub-GHz within 10m of target"
  },
  "hardware": {
    "flipper_zero": { "connected": true, "port": "/dev/ttyACM0" },
    "ble_adapter": { "connected": true, "type": "native" },
    "wifi_adapter": { "connected": false, "note": "no monitor mode" }
  },
  "iteration_count": 0,
  "max_iterations": 50,
  "findings": {},
  "failed_vectors": [],
  "current_vector_index": 0
}
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| Hardware validated + scope set | **RECONNAISSANCE** |
| No hardware available | **REPORTING** (partial — "no hardware" report) |
| Target spec invalid/unclear | Stay in **TARGET_ACQUISITION** (ask user to clarify) |

**Checkpoint:** Save initial state to `checkpoints/bellum-{id}-s1.json`

---

### S2: RECONNAISSANCE

**Description:** Broad surface discovery. Cast a wide net across all available protocols to find what the target exposes. This phase is about *breadth*, not depth.

**Goal:** Populate `findings.surfaces[]` — the list of attack surfaces the target exposes.

**Tool access:**
| Tool | Purpose | Priority |
|------|---------|----------|
| `ble_scan` | Discover BLE devices broadcasting | HIGH — always run |
| `wifi_scan` | Discover WiFi networks | HIGH — if adapter available |
| `nmap_scan` | Discover open ports/services on known IPs | HIGH — if IP known |
| `subghz_scan` | Listen for Sub-GHz signals | MEDIUM — if Flipper available |
| `ir_capture` | Listen for IR signals | LOW — situational |
| `shodan_search` | Find target on Shodan if internet-facing | MEDIUM — if IP known |

**Recon completion criteria (exit when ANY are true):**
- All available protocol scanners have been run at least once
- At least 2 distinct attack surfaces discovered
- 10 tool calls executed in this phase (breadth cap)

**Output structure (compressed for next phase):**
```json
{
  "surfaces": [
    {
      "protocol": "BLE",
      "identifier": "QUADRUPED-AA:BB:CC:DD:EE:FF",
      "rssi": -45,
      "details": "advertising, connectable, name=QUADRUPED-XX"
    },
    {
      "protocol": "TCP",
      "identifier": "192.168.4.1:8080",
      "details": "HTTP server, nginx, no auth challenge"
    },
    {
      "protocol": "TCP",
      "identifier": "192.168.4.1:22",
      "details": "SSH OpenSSH 8.9"
    }
  ],
  "no_results": ["SubGHz", "IR"],
  "hardware_issues": ["WiFi monitor mode unavailable"]
}
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| >= 1 surface found | **RESEARCH** |
| 0 surfaces after all scanners exhausted | **REPORTING** (partial — "no surfaces found") |
| Tool failure (hardware disconnect) | **RECOVERY** |
| Iteration cap hit | **REPORTING** (partial) |

**Checkpoint:** Save `findings.surfaces` to `checkpoints/bellum-{id}-s2.json`

---

### S3: RESEARCH

**Description:** Enrich reconnaissance findings with open-source intelligence. For each discovered surface, search for known vulnerabilities, existing exploits, documentation, and teardowns. This phase is about *context*, not access.

**Goal:** Populate `findings.intel[]` — vulnerability intel and attack hypotheses for each surface.

**Tool access:**
| Tool | Purpose | Priority |
|------|---------|----------|
| `web_search` | Search for "{device} {protocol} vulnerability" | HIGH |
| `github_search` | Search for existing exploit code | HIGH |
| `cve_search` | Look up CVEs for identified services/versions | HIGH |
| `fcc_lookup` | Get RF specs for device (if FCC ID visible) | MEDIUM |
| `web_fetch` | Read specific pages (teardowns, docs, CVE details) | MEDIUM |

**Research completion criteria:**
- Each surface has been researched (at least 1 search per surface)
- At least 1 attack hypothesis formed
- 15 tool calls executed in this phase (depth cap)

**Output structure:**
```json
{
  "intel": [
    {
      "surface": "BLE:QUADRUPED-AA:BB:CC:DD:EE:FF",
      "findings": [
        "BLE GATT services likely unprotected (no bonding advertised)",
        "CVE-2025-XXXXX: {robot_brand} BLE command injection",
        "GitHub: existing Bleak script for this robot model"
      ],
      "attack_hypotheses": [
        "H1: Unauthenticated BLE GATT write to control characteristic",
        "H2: BLE MITM via spoofed peripheral"
      ]
    },
    {
      "surface": "TCP:192.168.4.1:8080",
      "findings": [
        "Web interface serves robot control panel",
        "No authentication on / or /api/ endpoints"
      ],
      "attack_hypotheses": [
        "H3: Unauthenticated API command injection"
      ]
    }
  ],
  "ranked_hypotheses": ["H1", "H3", "H2"]
}
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| >= 1 attack hypothesis formed | **ENUMERATION** |
| 0 hypotheses after research exhausted | **REPORTING** (partial — "no vulns found") |
| Iteration cap hit | **REPORTING** (partial) |

**Checkpoint:** Save `findings.intel` to `checkpoints/bellum-{id}-s3.json`

---

### S4: ENUMERATION

**Description:** Deep-dive into the most promising attack surfaces. Interact with the target to confirm hypotheses, discover exact parameters needed for exploitation. This phase is about *precision* — getting the exact characteristic UUIDs, API endpoints, command formats, and credential weaknesses needed to build an exploit.

**Goal:** Populate `findings.vectors[]` — confirmed, actionable attack vectors with all parameters needed for exploitation.

**Tool access:**
| Tool | Purpose | Priority |
|------|---------|----------|
| `ble_enumerate` | Full GATT service/characteristic dump | HIGH |
| `ble_read_char` | Read specific characteristics | HIGH |
| `ble_subscribe` | Monitor notifications for command/response patterns | MEDIUM |
| `http_request` | Probe API endpoints, check auth, enumerate routes | HIGH |
| `packet_analyze` | Analyze captured traffic for protocol details | MEDIUM |
| `wifi_capture` | Capture traffic between robot and controller | MEDIUM |
| `ssh_connect` | Try default/discovered credentials | MEDIUM |
| `code_execute` | Run custom scripts for protocol analysis | LOW |

**Enumeration process per hypothesis:**
1. Interact with the target surface (connect, enumerate, probe)
2. Confirm or reject the hypothesis
3. If confirmed: extract exact attack parameters
4. If rejected: mark hypothesis as failed, move to next

**Output structure:**
```json
{
  "vectors": [
    {
      "id": "V1",
      "hypothesis": "H1",
      "confirmed": true,
      "type": "BLE unauthenticated GATT write",
      "target": "AA:BB:CC:DD:EE:FF",
      "parameters": {
        "service_uuid": "0000ffe0-0000-1000-8000-00805f9b34fb",
        "char_uuid": "0000ffe1-0000-1000-8000-00805f9b34fb",
        "properties": ["write", "write-without-response", "notify"],
        "sample_command": "0x01 0x02 ... (movement forward)",
        "protocol_notes": "Little-endian, first byte = command type, bytes 2-3 = parameter"
      },
      "severity": "CRITICAL",
      "confidence": "HIGH"
    },
    {
      "id": "V2",
      "hypothesis": "H3",
      "confirmed": true,
      "type": "Unauthenticated REST API",
      "target": "192.168.4.1:8080",
      "parameters": {
        "endpoint": "/api/cmd",
        "method": "POST",
        "content_type": "application/json",
        "sample_payload": {"action": "move", "direction": "forward", "speed": 50}
      },
      "severity": "CRITICAL",
      "confidence": "HIGH"
    }
  ],
  "rejected_hypotheses": [],
  "vector_priority": ["V1", "V2"]
}
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| >= 1 confirmed vector | **EXPLOITATION** (attempt highest-priority vector) |
| 0 confirmed vectors, hypotheses remain | Back to **RESEARCH** (broaden search) |
| 0 confirmed vectors, no hypotheses remain | **REPORTING** (partial — "no exploitable vectors") |
| Iteration cap hit | **REPORTING** (partial) |

**Checkpoint:** Save `findings.vectors` to `checkpoints/bellum-{id}-s4.json`

---

### S5: EXPLOITATION

**Description:** Craft and execute a proof-of-concept exploit for the current attack vector. This is the payoff — demonstrate actual impact on the target.

**Goal:** Achieve a demonstrable effect on the target (movement, data exfil, service disruption, unauthorized access).

**CRITICAL: Human-in-the-loop gate.** Before any exploit execution, the agent MUST present the exploit plan and wait for confirmation. This is enforced via OpenCode's `permission.ask` plugin hook.

**Tool access:**
| Tool | Purpose | HITL Required? |
|------|---------|---------------|
| `ble_write_char` | Send crafted BLE command | **YES** |
| `subghz_replay` | Replay captured RF signal | **YES** |
| `ir_replay` | Replay captured IR signal | **YES** |
| `badusb_execute` | Execute HID payload | **YES** |
| `http_request` | Send exploit HTTP request | **YES** (if destructive) |
| `ssh_connect` | Login with discovered creds | **YES** |
| `code_execute` | Run crafted exploit script | **YES** |
| `ble_read_char` | Verify post-exploit state | No |
| `web_search` | Find exploit reference code | No |

**Exploitation process:**
1. Select highest-priority unexhausted vector from `vector_priority`
2. Craft exploit payload using vector parameters + research intel
3. **PRESENT EXPLOIT PLAN** — show the user exactly what will be sent
4. **WAIT FOR CONFIRMATION** — do not proceed without explicit approval
5. Execute exploit
6. Observe result — did the target respond as expected?
7. If successful: document the impact, attempt to escalate if possible
8. If failed: analyze why, adjust payload, retry (max 3 attempts per vector)

**Output structure (on success):**
```json
{
  "exploit": {
    "vector_id": "V1",
    "payload_sent": "ble_write_char(AA:BB:CC:DD:EE:FF, 0xFFE1, 0x01020032)",
    "result": "Robot moved forward at speed 50",
    "impact": "Full unauthorized movement control via BLE",
    "evidence": "Robot physically moved. Confirmed visual observation.",
    "escalation_attempted": true,
    "escalation_result": "Also achieved emergency stop (0x00) and direction reversal"
  }
}
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| Exploit succeeds (demonstrable impact) | **REPORTING** |
| Exploit fails after 3 retries on current vector | **PIVOT** |
| User denies HITL confirmation | **REPORTING** (partial — "exploit ready but not executed") |
| Iteration cap hit | **REPORTING** (partial) |

**Checkpoint:** Save exploit attempt + result to `checkpoints/bellum-{id}-s5.json`

---

### S6: PIVOT

**Description:** Current attack vector failed. Evaluate remaining vectors and decide whether to try the next one or broaden the search.

**This is NOT a long-running state.** It's a decision point — one reasoning step, then transition.

**Decision logic:**
```
remaining_vectors = vectors where attempted == false
consecutive_failures += 1

IF remaining_vectors is not empty:
    current_vector = remaining_vectors[0]
    consecutive_failures = 0
    → EXPLOITATION (with new vector)

ELIF consecutive_failures < 3 AND recon_surfaces exist with no hypotheses:
    → RECONNAISSANCE (re-scan with different parameters)

ELIF consecutive_failures < 3 AND hypotheses exist that weren't fully researched:
    → RESEARCH (dig deeper)

ELSE:
    → REPORTING (partial — "all vectors exhausted")
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| More vectors available | **EXPLOITATION** |
| No vectors, unexplored surfaces remain | **RECONNAISSANCE** |
| No vectors, unresearched hypotheses remain | **RESEARCH** |
| Everything exhausted | **REPORTING** |

---

### S7: REPORTING

**Description:** Generate a structured pentest report from all findings, regardless of whether exploitation succeeded.

**Entry conditions:** Any terminal transition (success, exhaustion, cap hit, user abort).

**Report structure:**
```markdown
# Adversarial Evaluation Report
## Engagement: {engagement_id}
## Target: {target.description}
## Date: {timestamp}
## Agent: Bellum v1.0

### Executive Summary
{1-2 sentence summary of outcome}

### Scope
- Target: {description}
- Hardware used: {hardware inventory}
- Protocols tested: {list}
- Duration: {elapsed time}
- Total agent iterations: {count}

### Findings

#### Attack Surfaces Discovered
{table of surfaces from RECON phase}

#### Vulnerability Research
{summary of intel from RESEARCH phase}

#### Confirmed Vectors
{table of confirmed vectors from ENUMERATION phase}

#### Exploitation Results
{details of exploit attempts from EXPLOITATION phase}

### Severity Assessment
| Finding | Severity | CVSS | Description |
|---------|----------|------|-------------|
| ... | CRITICAL/HIGH/MEDIUM/LOW | x.x | ... |

### Recommendations
{for each finding, a remediation recommendation}

### Attack Chain Visualization
{step-by-step chain that was executed}

### Failed Vectors
{what was tried and didn't work — useful for scope documentation}

### Appendix
- Raw tool outputs (truncated)
- Timeline of agent actions
```

**Transitions:**
| Condition | Next State |
|-----------|------------|
| Report generated | **COMPLETE** |

---

### S8: COMPLETE

**Description:** Engagement finished. Report saved. Agent returns to idle.

**Actions:**
1. Save final report to `reports/bellum-{id}-report.md`
2. Save full checkpoint history
3. Display summary to user
4. Return to **IDLE**

---

### S9: RECOVERY

**Description:** Something went wrong at the infrastructure level — not a normal tool failure (those are handled inline), but a systemic issue that breaks the current state.

**Trigger conditions:**
| Trigger | Detection | Recovery Action |
|---------|-----------|-----------------|
| Flipper Zero disconnected | Serial timeout/error | Attempt reconnection 3x (2s backoff). If fails: remove Flipper tools from available set, continue with laptop-native tools only. |
| BLE adapter failure | Bleak connection error | Reset adapter (`hciconfig reset`), retry. If fails: mark BLE vectors as "hardware unavailable". |
| LLM provider error (rate limit, 500, timeout) | HTTP error from API | Switch to fallback provider. If all providers fail: save checkpoint, pause, alert user. |
| Context window overflow | Token count > 80% of max | Compress all phase findings to JSON summaries. Drop raw tool outputs older than last 5 interactions. Resume. |
| Agent stuck (same tool call 3x with identical params) | Detected by plugin hook `tool.execute.before` | Inject "PIVOT: you are repeating yourself" into context. Force state transition to PIVOT. |
| Agent stuck (10 tool calls with no state variable changes) | Detected by plugin hook | Inject progress check: "Summarize what you've learned. Update your attack plan. If stuck, move to REPORTING." |

**Recovery is not a state the agent "enters" in the traditional sense.** It's a set of interrupt handlers that fire, fix the issue, and return the agent to its previous state. Only if recovery fails does the agent transition to REPORTING (partial).

**Transitions:**
| Condition | Next State |
|-----------|------------|
| Recovery succeeds | Return to previous state |
| Recovery fails | **REPORTING** (partial) |

---

## Global Constraints (enforced across all states)

### Iteration Budget

```
max_iterations = 50 (total tool calls across all states)
iteration_budget_per_state = {
    TARGET_ACQUISITION: 5,
    RECONNAISSANCE:     10,
    RESEARCH:           15,
    ENUMERATION:        10,
    EXPLOITATION:       8,  (per vector, resets on PIVOT)
    PIVOT:              1,  (decision only, no tool calls)
    REPORTING:          3,
}
```

When a state exhausts its budget, the agent MUST transition. No exceptions.
When total iterations hit 45, the agent MUST transition to REPORTING regardless of current state (5 iterations reserved for report generation).

### Consecutive Failure Limit

If `consecutive_tool_failures >= 5` in any single state, force transition:
- From RECON/RESEARCH/ENUMERATION → REPORTING (partial)
- From EXPLOITATION → PIVOT

### Context Window Management

After each state transition, the agent MUST produce a **phase summary** (the JSON structures shown above). Raw tool outputs from the completed phase are dropped from active context. Only the compressed summary carries forward.

This is critical: a full nmap output is ~2000 tokens. A BLE GATT enumeration is ~1500 tokens. A web page fetch is ~3000 tokens. Without compression, the agent blows through 128K context in ~15 tool calls.

### Checkpoint Protocol

After EVERY state transition, save:
```json
{
  "engagement_id": "...",
  "current_state": "RESEARCH",
  "timestamp": "2026-03-08T14:23:00Z",
  "iteration_count": 12,
  "findings": { /* accumulated */ },
  "failed_vectors": [],
  "hardware_status": { /* current */ },
  "last_5_tool_calls": [ /* for context restoration */ ]
}
```

If the agent crashes, resume with: "You are Bellum. You were conducting engagement {id}. Current state: {state}. Findings so far: {findings}. Continue from where you left off."

---

## State Transition Diagram (Compact)

```
IDLE ─────► TARGET_ACQUISITION ─────► RECONNAISSANCE ─────► RESEARCH
                                           ▲                    │
                                           │                    ▼
                                        PIVOT ◄──── ENUMERATION
                                           │              │
                                           ▼              ▼
                                      EXPLOITATION ──► REPORTING ──► COMPLETE
                                           │              ▲
                                           └──────────────┘
                                         (success or exhaustion)

RECOVERY can interrupt any state and either return to it or jump to REPORTING.
```

---

## Implementation in OpenCode

This state machine is NOT implemented as code inside OpenCode. It's implemented through:

### 1. System Prompt (in custom agent definition)
The state machine rules, transition conditions, and output formats are encoded in the agent's system prompt. The LLM acts as the state machine controller.

### 2. Skills (`.opencode/skills/`)
Each phase has a corresponding skill that the agent loads on-demand:
- `ble-recon/SKILL.md` — how to run BLE reconnaissance
- `rf-replay/SKILL.md` — how to capture and replay Sub-GHz signals
- `zero-knowledge-target/SKILL.md` — full blackbox assessment workflow (the master skill)

### 3. Plugin Hooks (`.opencode/plugins/`)
- `tool.execute.before` — stuck detection (repeated identical calls), audit logging
- `tool.execute.after` — output truncation, checkpoint writes
- `permission.ask` — HITL gate on exploitation tools

### 4. Custom Agents (`.opencode/agents/`)
Different agents for different phases, each with appropriate model + tool restrictions:
- `bellum-recon` — fast model, read-only tools, broad scanning
- `bellum-exploit` — strong reasoning model, all tools, HITL enforced
- `bellum-report` — fast model, no hardware tools, report generation only

### 5. State Persistence
OpenCode's SQLite session storage + custom checkpoint files in `checkpoints/`.
On crash recovery, the checkpoint is injected into a new session's system prompt.

---

## Example Trace

```
[S0:IDLE]
  User: "Attack that quadruped robot on the table"

[S1:TARGET_ACQUISITION]
  → Verify Flipper Zero on /dev/ttyACM0 ✓
  → Verify BLE adapter ✓
  → WiFi monitor mode ✗ (skipping WiFi deauth tools)
  → Set scope: BLE/WiFi/SubGHz within 10m
  CHECKPOINT: s1.json

[S2:RECONNAISSANCE] (budget: 10 calls)
  → ble_scan(duration=10) → 3 devices found, "QUADRUPED-XX" at -42 dBm
  → wifi_scan() → "RobotAP-5G" network found
  → nmap_scan(192.168.4.1) → ports 22, 8080, 9090 open
  → subghz_scan(300-900MHz, duration=15) → no signals
  PHASE SUMMARY: 3 surfaces (BLE, HTTP:8080, SSH:22), SubGHz/IR negative
  CHECKPOINT: s2.json
  → TRANSITION: surfaces found → RESEARCH

[S3:RESEARCH] (budget: 15 calls)
  → web_search("QUADRUPED robot BLE vulnerability") → 2 relevant results
  → web_fetch(teardown_article_url) → BLE uses no pairing, GATT writable
  → cve_search("QUADRUPED robot") → CVE-2025-XXXXX: BLE command injection
  → github_search("QUADRUPED BLE exploit") → existing Bleak PoC found
  → web_search("QUADRUPED 8080 API documentation") → REST API docs found
  PHASE SUMMARY: 3 hypotheses (H1: BLE GATT write, H2: BLE MITM, H3: REST API)
  Ranked: [H1, H3, H2]
  CHECKPOINT: s3.json
  → TRANSITION: hypotheses formed → ENUMERATION

[S4:ENUMERATION] (budget: 10 calls)
  → ble_enumerate(AA:BB:CC:DD:EE:FF) → GATT dump, 0xFFE1 is writable
  → ble_read_char(AA:BB:CC:DD:EE:FF, 0xFFE1) → current value: 0x00 (idle)
  → ble_subscribe(AA:BB:CC:DD:EE:FF, 0xFFE1) → notifications active
  → http_request(GET 192.168.4.1:8080/api/) → endpoint list, no auth
  → http_request(GET 192.168.4.1:8080/api/status) → robot state JSON
  PHASE SUMMARY: V1 confirmed (BLE write, no auth), V2 confirmed (REST API, no auth)
  Vector priority: [V1, V2]
  CHECKPOINT: s4.json
  → TRANSITION: vectors confirmed → EXPLOITATION

[S5:EXPLOITATION] (budget: 8 calls per vector)
  → Crafting BLE payload: 0x01 0x02 0x00 0x32 (move forward, speed 50)
  → *** HITL GATE: "I want to send BLE write to 0xFFE1: move robot forward. Approve?" ***
  → User: approved
  → ble_write_char(AA:BB:CC:DD:EE:FF, 0xFFE1, 0x01020032) → success
  → OBSERVE: robot physically moves forward ✓
  → ble_write_char(AA:BB:CC:DD:EE:FF, 0xFFE1, 0x00000000) → emergency stop
  → OBSERVE: robot stops ✓
  PHASE SUMMARY: Full movement control achieved via unauthenticated BLE
  CHECKPOINT: s5.json
  → TRANSITION: exploit succeeded → REPORTING

[S7:REPORTING] (budget: 3 calls)
  → Generate pentest report
  → Save to reports/bellum-20260308-001-report.md
  CHECKPOINT: s7.json
  → TRANSITION: report complete → COMPLETE

[S8:COMPLETE]
  → Display: "Engagement complete. CRITICAL: Unauthenticated BLE control.
     Full report: reports/bellum-20260308-001-report.md"
  → Return to IDLE

Total iterations used: 23 / 50
```
