# Bellum Agent State Machine v2

**Version:** 2.0
**Date:** 2026-02-26
**Architecture:** OpenCode fork + Ralph Wiggum loops + subagent orchestration

---

## Architecture Change from v1

v1 assumed the LLM self-manages state transitions via system prompts. That's fragile — the LLM forgets instructions, drifts, loops. v2 uses **external control structures** that guarantee convergence:

| Mechanism | What It Does | Source |
|-----------|-------------|--------|
| **Ralph loops** | Keep feeding the same phase prompt until completion criteria met | [ralph-wiggum plugin](https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/README.md) |
| **Backpressure gates** | Block phase transition until output validates | [ralph-orchestrator](https://github.com/mikeyobrien/ralph-orchestrator) |
| **Subagents (Task tool)** | Parallel execution within phases, isolated context windows | OpenCode built-in |
| **Built-in tools** | WebSearch, WebFetch, Bash, Read/Write, TodoWrite — already in OpenCode | OpenCode built-in |
| **OpenCode fork** | We own the orchestration layer, add ralph runner + custom tools | Our code |

**The key insight:** each phase of the attack chain is a ralph loop. The orchestrator (our fork code) runs the loops sequentially, validates output between them, and passes compressed findings forward. The LLM doesn't manage state — **we** manage state. The LLM just does the work within each phase.

---

## High-Level Flow

```
bellum "Attack that quadruped robot"
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BELLUM ORCHESTRATOR                              │
│                (ralph loop runner — our fork code)                   │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  PHASE 0 │───►│ PHASE 1  │───►│ PHASE 2  │───►│ PHASE 3  │     │
│  │  TARGET   │    │  RECON   │    │ RESEARCH │    │  ENUM    │     │
│  │ (1 shot) │    │ (loop)   │    │ (loop)   │    │ (loop)   │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│                                                        │            │
│       ┌────────────────────────────────────────────────┘            │
│       ▼                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                      │
│  │ PHASE 4  │───►│ PHASE 5  │───►│ PHASE 6  │                      │
│  │ EXPLOIT  │    │  PIVOT   │    │  REPORT  │                      │
│  │ (loop+   │    │(decision)│    │ (loop)   │                      │
│  │  HITL)   │    └──────────┘    └──────────┘                      │
│  └──────────┘         │                                             │
│       ▲               │ more vectors                                │
│       └───────────────┘                                             │
│                                                                     │
│  RECOVERY: interrupt handler, not a phase                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Orchestrator (Our Fork Code)

This is the code we add to OpenCode. It runs **outside** the LLM — it's deterministic control flow that calls the LLM inside ralph loops.

```python
# pseudocode — actual implementation is TypeScript in the OpenCode fork

async def run_engagement(target_spec: str):
    state = EngagementState(target=target_spec)

    # PHASE 0: Target acquisition (single-shot, no loop)
    state.hardware = await verify_hardware()
    state.scope = await parse_target(target_spec)
    checkpoint(state, "phase0")

    # PHASE 1: Reconnaissance (ralph loop)
    state.surfaces = await ralph_loop(
        agent="bellum-recon",
        prompt=RECON_PROMPT.format(target=state.scope, hardware=state.hardware),
        completion_promise="RECON_COMPLETE",
        max_iterations=10,
        backpressure_gate=lambda output: len(output.get("surfaces", [])) >= 1,
        output_file="findings/surfaces.json",
    )
    checkpoint(state, "phase1")

    if not state.surfaces:
        return await run_report(state, partial=True, reason="no surfaces found")

    # PHASE 2: Research (ralph loop with parallel subagents inside)
    state.intel = await ralph_loop(
        agent="bellum-research",
        prompt=RESEARCH_PROMPT.format(surfaces=state.surfaces),
        completion_promise="RESEARCH_COMPLETE",
        max_iterations=15,
        backpressure_gate=lambda output: len(output.get("hypotheses", [])) >= 1,
        output_file="findings/intel.json",
    )
    checkpoint(state, "phase2")

    if not state.intel.get("hypotheses"):
        return await run_report(state, partial=True, reason="no hypotheses formed")

    # PHASE 3: Enumeration (ralph loop)
    state.vectors = await ralph_loop(
        agent="bellum-enumerate",
        prompt=ENUM_PROMPT.format(surfaces=state.surfaces, intel=state.intel),
        completion_promise="ENUM_COMPLETE",
        max_iterations=10,
        backpressure_gate=lambda output: len(output.get("vectors", [])) >= 1,
        output_file="findings/vectors.json",
    )
    checkpoint(state, "phase3")

    if not state.vectors:
        return await run_report(state, partial=True, reason="no vectors confirmed")

    # PHASE 4+5: Exploitation + Pivot loop
    for vector in state.vectors:
        result = await ralph_loop(
            agent="bellum-exploit",
            prompt=EXPLOIT_PROMPT.format(vector=vector, intel=state.intel),
            completion_promise="EXPLOIT_COMPLETE",
            max_iterations=8,
            hitl_gate=True,  # MUST approve before execution
            backpressure_gate=lambda output: output.get("impact") is not None,
            output_file=f"findings/exploit_{vector['id']}.json",
        )
        if result.get("success"):
            state.exploit_results.append(result)
            break  # got a win, move to report
        else:
            state.failed_vectors.append(vector)
            continue  # PIVOT: try next vector

    # PHASE 6: Report (ralph loop)
    report = await ralph_loop(
        agent="bellum-report",
        prompt=REPORT_PROMPT.format(state=state),
        completion_promise="REPORT_COMPLETE",
        max_iterations=3,
        output_file=f"reports/bellum-{state.engagement_id}.md",
    )

    return report
```

**This is ~50 lines of deterministic control flow.** The LLM does the hard work inside each ralph loop. The orchestrator just sequences the phases, validates output, and handles pivot logic.

---

## Ralph Loop Mechanics

Each phase runs as a ralph loop. Here's how it works:

```
ralph_loop(agent, prompt, completion_promise, max_iterations, backpressure_gate)
│
├── Iteration 1:
│   ├── Feed prompt to agent
│   ├── Agent uses tools (Bash, WebSearch, ble_scan, etc.)
│   ├── Agent writes findings to output_file
│   ├── Agent outputs "RECON_COMPLETE" (or not)
│   └── Stop hook intercepts exit
│       ├── Check: did agent output completion_promise? → YES → exit loop
│       ├── Check: does output_file pass backpressure_gate? → YES → exit loop
│       ├── Check: iteration >= max_iterations? → YES → exit loop (partial)
│       └── NO to all → re-feed same prompt, agent sees its previous work in files
│
├── Iteration 2:
│   ├── Agent reads its own previous output from files
│   ├── Agent sees what it already did (git diff / file state)
│   ├── Agent continues where it left off or tries different approach
│   └── Stop hook checks again...
│
└── ... until exit condition met
```

**Why this is better than v1's LLM-managed state:**
1. The LLM can't forget the state machine rules — they're enforced externally
2. The LLM can't loop forever — max_iterations is a hard cap
3. The LLM can't skip validation — backpressure_gate blocks progression
4. Fresh context each iteration — no context window blowout
5. File-based memory — findings persist between iterations via disk, not token context

---

## Phase Definitions

### Phase 0: Target Acquisition (Single-Shot)

**Not a ralph loop** — this is deterministic code that runs once.

```typescript
// In the orchestrator (our fork code)
async function acquireTarget(spec: string): Promise<EngagementState> {
    const hardware = {
        flipper: await checkSerial("/dev/ttyACM0"),
        ble: await checkBleAdapter(),
        wifi: await checkWifiMonitor(),
    };

    return {
        engagement_id: `bellum-${Date.now()}`,
        target: spec,
        hardware,
        available_tools: deriveToolset(hardware), // only enable tools for connected hardware
    };
}
```

**Output:** `findings/target.json` — hardware inventory + scope

---

### Phase 1: Reconnaissance (Ralph Loop)

**Agent:** `bellum-recon` (fast model — Kimi K2.5 or MiniMax M2.5)

**Prompt:**
```
You are a reconnaissance agent for a cyber-physical security evaluation.

TARGET: {target_spec}
HARDWARE AVAILABLE: {hardware_inventory}
PREVIOUS FINDINGS: Read findings/surfaces.json if it exists.

Your mission: discover ALL wireless and network attack surfaces the target
exposes. Cast a wide net — BLE, WiFi, network ports, Sub-GHz RF.

Available tools:
- Bash: run `python3 scripts/ble_scan.py`, `nmap`, `python3 scripts/wifi_scan.py`
- WebSearch: look up the target model/brand if you can identify it
- Read/Write: read previous findings, write updated findings

For each discovered surface, record: protocol, identifier, signal strength, details.

Write your findings to findings/surfaces.json in this format:
{surfaces_schema}

When you have run all available scanners and documented all surfaces,
output <promise>RECON_COMPLETE</promise>
```

**Subagent parallelism within this phase:**
```
bellum-recon (parent)
├── Task("Scan BLE devices for 15 seconds") → runs ble_scan.py via Bash
├── Task("Run nmap -sV against 192.168.0.0/24") → runs nmap via Bash
└── Task("Scan Sub-GHz 300-900MHz for 20s") → runs subghz_scan.py via Bash
    (all three run in parallel via OpenCode's Task tool)
```

**Backpressure gate:** `surfaces.json` exists AND contains >= 1 surface
**Max iterations:** 10
**Checkpoint:** `checkpoints/phase1.json`

---

### Phase 2: Research (Ralph Loop)

**Agent:** `bellum-research` (strong reasoning model — Claude or Kimi K2.5)

**Prompt:**
```
You are a vulnerability researcher for a cyber-physical security evaluation.

DISCOVERED SURFACES: {read findings/surfaces.json}
PREVIOUS RESEARCH: Read findings/intel.json if it exists.

Your mission: for each attack surface, search for known vulnerabilities,
existing exploits, documentation, and teardowns. Form attack hypotheses.

Available tools:
- WebSearch: search for "{device} {protocol} vulnerability 2025 2026"
- WebFetch: read specific vulnerability pages, teardowns, documentation
- Bash: run `python3 scripts/cve_search.py {product}`, `python3 scripts/shodan_search.py {query}`,
         `python3 scripts/github_search.py {query}`, `python3 scripts/fcc_lookup.py {fcc_id}`
- Read/Write: read surfaces, write intel

For each surface, research and record findings + attack hypotheses.
Rank hypotheses by likelihood of success.

Write findings to findings/intel.json in this format:
{intel_schema}

When all surfaces have been researched, output <promise>RESEARCH_COMPLETE</promise>
```

**Subagent parallelism:**
```
bellum-research (parent)
├── Task("Research BLE surface: {surface_1}") → WebSearch + cve_search + github_search
├── Task("Research HTTP surface: {surface_2}") → WebSearch + WebFetch + shodan_search
└── Task("Research SSH surface: {surface_3}") → WebSearch + cve_search
    (one subagent per surface, all parallel)
```

**Backpressure gate:** `intel.json` exists AND contains >= 1 hypothesis
**Max iterations:** 15
**Checkpoint:** `checkpoints/phase2.json`

---

### Phase 3: Enumeration (Ralph Loop)

**Agent:** `bellum-enumerate` (strong model — needs to reason about protocols)

**Prompt:**
```
You are an enumeration specialist for a cyber-physical security evaluation.

SURFACES: {read findings/surfaces.json}
INTEL: {read findings/intel.json}
PREVIOUS VECTORS: Read findings/vectors.json if it exists.

Your mission: deep-dive the top-ranked attack hypotheses. Interact with the
target to confirm or reject each hypothesis. For confirmed hypotheses, extract
the exact parameters needed for exploitation.

Available tools:
- Bash: run `python3 scripts/ble_enumerate.py {mac}`, `python3 scripts/ble_read.py {mac} {uuid}`,
         `curl`, `ssh`, `python3 scripts/packet_analyze.py {pcap}`
- Read/Write: read intel, write vectors

For each hypothesis:
1. Interact with the target surface
2. Confirm or reject
3. If confirmed: record exact attack parameters (UUIDs, endpoints, payloads)
4. If rejected: record why and move to next

Write findings to findings/vectors.json in this format:
{vectors_schema}

When all hypotheses have been tested, output <promise>ENUM_COMPLETE</promise>
```

**Backpressure gate:** `vectors.json` exists AND contains >= 1 confirmed vector
**Max iterations:** 10
**Checkpoint:** `checkpoints/phase3.json`

---

### Phase 4: Exploitation (Ralph Loop + HITL Gate)

**Agent:** `bellum-exploit` (strongest reasoning model available)

**This phase has a HITL gate.** The orchestrator intercepts tool calls to dangerous tools (ble_write, subghz_replay, http POST to target, code_execute) and requires human approval via OpenCode's `permission.ask` hook before execution.

**Prompt:**
```
You are an exploit developer for a cyber-physical security evaluation.

VECTOR: {current_vector from vectors.json}
INTEL: {relevant intel for this vector}
PREVIOUS ATTEMPTS: Read findings/exploit_{vector_id}.json if it exists.

Your mission: craft and execute a proof-of-concept exploit for this vector.
Demonstrate actual impact on the target.

Available tools:
- Bash: run `python3 scripts/ble_write.py {mac} {uuid} {payload}`,
         `python3 scripts/subghz_replay.py {file}`, `curl`, custom scripts
- WebSearch: find reference exploit code
- Read/Write: read vector details, write exploit results

Process:
1. Study the vector parameters
2. Craft the exploit payload
3. IMPORTANT: Before executing, clearly state what you will send and why
4. Execute the exploit
5. Observe and document the result
6. If failed: analyze why, adjust, retry (you have multiple iterations)

Write results to findings/exploit_{vector_id}.json in this format:
{exploit_schema}

When you have demonstrated impact OR exhausted approaches,
output <promise>EXPLOIT_COMPLETE</promise>
```

**HITL enforcement (OpenCode plugin hook):**
```typescript
// .opencode/plugins/hitl-gate.ts
export default {
    name: "bellum-hitl",
    hooks: {
        "tool.execute.before": async (ctx) => {
            const dangerous = ["ble_write", "subghz_replay", "ir_replay",
                               "badusb_execute"];
            const cmd = ctx.tool.input?.command || "";

            // Check if Bash is running a dangerous script
            if (ctx.tool.name === "Bash" &&
                dangerous.some(d => cmd.includes(d))) {
                return {
                    action: "require_approval",
                    message: `EXPLOIT EXECUTION: ${cmd}\nApprove?`
                };
            }
        }
    }
};
```

**Backpressure gate:** `exploit_{id}.json` exists AND `impact` field is non-null
**Max iterations:** 8 per vector
**Checkpoint:** `checkpoints/phase4_{vector_id}.json`

---

### Phase 5: Pivot (Deterministic Code, Not a Loop)

**Not a ralph loop.** This is orchestrator logic:

```python
# In the orchestrator
for vector in state.vectors:
    result = await run_exploit_loop(vector)
    if result.success:
        state.successful_exploits.append(result)
        break
    else:
        state.failed_vectors.append(vector)
        # Continue to next vector (the for loop IS the pivot)

# If no vectors succeeded but we haven't explored all surfaces:
if not state.successful_exploits and unexplored_surfaces(state):
    # Re-run recon with different parameters
    state.surfaces = await ralph_loop(agent="bellum-recon", ...)
    # Then re-run research, enum, exploit...
```

The for loop over vectors IS the pivot logic. No LLM decision needed.

---

### Phase 6: Reporting (Ralph Loop)

**Agent:** `bellum-report` (fast model — just needs to write well)

**Prompt:**
```
You are a security report writer.

Read ALL findings files in findings/ directory:
- findings/target.json (target + hardware)
- findings/surfaces.json (discovered attack surfaces)
- findings/intel.json (vulnerability research)
- findings/vectors.json (confirmed attack vectors)
- findings/exploit_*.json (exploitation results)

Generate a professional penetration test report.

Write the report to reports/bellum-{engagement_id}.md using this structure:
{report_template}

Include severity ratings (CRITICAL/HIGH/MEDIUM/LOW), remediation
recommendations, and an attack chain visualization.

When the report is complete, output <promise>REPORT_COMPLETE</promise>
```

**Backpressure gate:** report file exists AND contains all required sections
**Max iterations:** 3
**Checkpoint:** `checkpoints/phase6.json`

---

## Tool Architecture

### What OpenCode Gives Us (Use Directly)

| OpenCode Tool | How Bellum Uses It |
|---------------|--------------------|
| **Bash** | THE BRIDGE TO EVERYTHING. Runs Python scripts (Bleak, pyFlipper, Scapy), nmap, tshark, curl, ssh, binwalk. Every hardware tool is a Python script invoked via Bash. |
| **WebSearch** | OSINT: search for device vulnerabilities, CVEs, teardowns, exploit code |
| **WebFetch** | Read vulnerability pages, documentation, API docs, GitHub READMEs |
| **Read** | Read findings files, captured data, configs, firmware dumps |
| **Write** | Write findings JSON, exploit scripts, reports |
| **Edit** | Modify exploit code between iterations |
| **Grep** | Search through captured packet data, firmware strings, config files |
| **Glob** | Find pcap files, firmware images, .sub files in the workspace |
| **Task** | Spawn subagents for parallel recon/research within a phase |
| **TodoWrite** | Track attack progress through phases (visible in TUI) |

**We do NOT need custom OpenCode tools for:** web search, web fetch, file I/O, code execution, search, or subagent delegation. That's half the PRD's tool list — free.

### What We Add (Python Scripts Called via Bash)

These live in `scripts/` and are invoked by the agent via Bash:

```
scripts/
├── hardware/
│   ├── ble_scan.py          # Bleak: scan BLE devices, output JSON
│   ├── ble_enumerate.py     # Bleak: full GATT enumeration, output JSON
│   ├── ble_read.py          # Bleak: read characteristic, output value
│   ├── ble_write.py         # Bleak: write characteristic (HITL gated)
│   ├── ble_subscribe.py     # Bleak: subscribe to notifications, output stream
│   ├── flipper_serial.py    # pyFlipper: generic serial command interface
│   ├── subghz_scan.py       # pyFlipper: Sub-GHz scanner, output JSON
│   ├── subghz_capture.py    # pyFlipper: capture signal to .sub file
│   ├── subghz_replay.py     # pyFlipper: replay .sub file (HITL gated)
│   ├── ir_capture.py        # pyFlipper: capture IR signal
│   ├── ir_replay.py         # pyFlipper: replay IR signal (HITL gated)
│   └── wifi_scan.py         # scapy/iwlist: scan WiFi networks, output JSON
├── recon/
│   ├── cve_search.py        # NVD API: search CVEs by product/version
│   ├── shodan_search.py     # Shodan API: search/host lookup
│   ├── github_search.py     # GitHub API: search repos/code/issues
│   └── fcc_lookup.py        # FCC API: lookup device RF specs
└── util/
    ├── packet_analyze.py    # pyshark: analyze pcap file, output summary
    └── firmware_analyze.py  # binwalk: extract/analyze firmware binary
```

**Every script follows the same contract:**
- Takes arguments from CLI: `python3 scripts/ble_scan.py --duration 10 --output json`
- Outputs structured JSON to stdout
- Returns exit code 0 on success, non-zero on failure
- Stderr for error messages

**The agent calls them via Bash:**
```
Bash: python3 scripts/hardware/ble_scan.py --duration 15
```

No TypeScript tool wrappers. No MCP servers for basic tools. Just Python scripts called via Bash. The agent can also write and run ad-hoc Python scripts via Bash for novel exploit development — it's not limited to our pre-built scripts.

### MCP Servers (For Complex Stateful Integrations)

Some tools need persistent connections or stateful sessions. These are MCP servers:

```json
// opencode.json
{
    "mcp": {
        "flipper-zero": {
            "type": "local",
            "command": ["python3", "mcp_servers/flipper_mcp.py"],
            "enabled": true,
            "environment": {
                "FLIPPER_PORT": "/dev/ttyACM0"
            }
        }
    }
}
```

Use MCP when:
- The tool needs a persistent serial connection (Flipper Zero)
- The tool has complex multi-step state (BLE connection that must stay alive across multiple reads/writes)

Use Bash scripts when:
- The tool is stateless (scan, search, one-shot read/write)
- The tool is a CLI wrapper (nmap, tshark, binwalk)

---

## Subagent Orchestration

### Within-Phase Parallelism

Inside a ralph loop iteration, the agent can spawn parallel subagents via the Task tool. This is OpenCode's native capability — we don't need to modify it.

**Recon phase — parallel scanning:**
```
bellum-recon iteration 1:
  "I need to scan BLE, WiFi, and network simultaneously."
  ├── Task("Run BLE scan for 15 seconds")
  │   └── Bash: python3 scripts/hardware/ble_scan.py --duration 15
  ├── Task("Run nmap against 192.168.0.0/24")
  │   └── Bash: nmap -sV 192.168.0.0/24
  └── Task("Run Sub-GHz scan 300-900MHz")
      └── Bash: python3 scripts/hardware/subghz_scan.py --range 300-900

  All three return results → agent merges into surfaces.json
```

**Research phase — parallel OSINT per surface:**
```
bellum-research iteration 1:
  "I need to research 3 surfaces in parallel."
  ├── Task("Research BLE:QUADRUPED-XX vulnerability and exploits")
  │   └── WebSearch + WebFetch + cve_search + github_search
  ├── Task("Research HTTP:192.168.4.1:8080 vulnerability")
  │   └── WebSearch + WebFetch + shodan_search
  └── Task("Research SSH:192.168.4.1:22 default credentials")
      └── WebSearch + cve_search

  All three return intel → agent merges into intel.json
```

### Across-Phase Orchestration

The orchestrator (our fork code) handles phase sequencing. Each phase is a ralph loop. Output files are the interface between phases.

```
Phase 1 (recon) writes → findings/surfaces.json
                              ↓ (read by)
Phase 2 (research) writes → findings/intel.json
                              ↓ (read by)
Phase 3 (enum) writes → findings/vectors.json
                              ↓ (read by)
Phase 4 (exploit) writes → findings/exploit_V1.json
                              ↓ (read by)
Phase 6 (report) writes → reports/bellum-{id}.md
```

**Files are the shared memory.** No token context carries between phases. Each phase starts fresh and reads what it needs from disk. This is the ralph loop's superpower — infinite effective context via filesystem.

---

## Recovery Architecture

### Per-Iteration Recovery (Inside Ralph Loop)

The ralph loop handles this automatically:
- If the agent crashes mid-iteration → loop restarts with same prompt, agent reads files from disk
- If the agent gets stuck → max_iterations cap kills the loop, orchestrator moves to next phase
- If a tool fails → agent sees the error in next iteration, tries different approach

### Hardware Recovery (Plugin Hook)

```typescript
// .opencode/plugins/hardware-recovery.ts
export default {
    name: "bellum-hardware-recovery",
    hooks: {
        "tool.execute.after": async (ctx) => {
            if (ctx.result?.error?.includes("serial") ||
                ctx.result?.error?.includes("ConnectionError") ||
                ctx.result?.error?.includes("BLEError")) {

                // Attempt hardware reconnection
                const recovered = await reconnectHardware(ctx);
                if (!recovered) {
                    // Write hardware status to disk so next iteration sees it
                    await writeFile("findings/hardware_status.json", {
                        [deviceType]: "disconnected",
                        timestamp: Date.now()
                    });
                }
            }
        }
    }
};
```

### Backpressure Gate Failures

If a phase hits max_iterations without passing the backpressure gate:

```python
# In the orchestrator
result = await ralph_loop(agent="bellum-recon", ...)

if not backpressure_gate(result):
    # Phase failed to produce valid output
    if phase == "recon" and no_surfaces:
        # Can't continue — nothing to research
        return await run_report(state, partial=True, reason="no surfaces found")
    elif phase == "research" and no_hypotheses:
        # Re-run recon with broader parameters?
        state.recon_params.broaden()
        continue  # re-enter recon loop
    elif phase == "exploit" and current_vector_failed:
        # Try next vector (pivot)
        continue  # for loop advances to next vector
```

---

## What We Fork in OpenCode

Minimal changes to OpenCode's codebase. We add, not modify:

### 1. Bellum Orchestrator (`packages/opencode/src/bellum/`)

```
packages/opencode/src/bellum/
├── orchestrator.ts     # Phase sequencing, ralph loop runner
├── state.ts            # EngagementState type definitions
├── gates.ts            # Backpressure gate validators
├── checkpoints.ts      # Checkpoint save/load
└── prompts/
    ├── recon.md        # Phase 1 prompt template
    ├── research.md     # Phase 2 prompt template
    ├── enumerate.md    # Phase 3 prompt template
    ├── exploit.md      # Phase 4 prompt template
    └── report.md       # Phase 6 prompt template
```

### 2. Ralph Loop Runner (`packages/opencode/src/bellum/ralph.ts`)

Implements the ralph loop pattern inside OpenCode:
- Feed prompt to agent
- Stop hook blocks exit
- Check completion promise / backpressure gate
- Re-feed or exit

### 3. CLI Entry Point

```bash
# Instead of `opencode "prompt"`, we add:
bellum "Attack that quadruped robot"
# This invokes the orchestrator, which runs the phases
```

### 4. Skills (`.opencode/skills/`)

Loaded on-demand by agents within phases:

```
.opencode/skills/
├── ble-recon/SKILL.md        # How to run BLE reconnaissance
├── ble-exploit/SKILL.md      # How to exploit BLE GATT vulnerabilities
├── rf-replay/SKILL.md        # How to capture and replay Sub-GHz signals
├── network-recon/SKILL.md    # How to run network recon (nmap, Shodan)
├── osint/SKILL.md            # How to research a device (web, GitHub, CVE)
└── report-writing/SKILL.md   # How to write a pentest report
```

### 5. Plugins (`.opencode/plugins/`)

```
.opencode/plugins/
├── hitl-gate.ts              # Block dangerous tool execution without approval
├── hardware-recovery.ts      # Auto-reconnect on hardware failures
├── audit-log.ts              # Log every tool call for the engagement record
└── stuck-detection.ts        # Detect repeated identical tool calls
```

---

## Example Trace (v2 — with ralph loops and subagents)

```
$ bellum "Attack that quadruped robot on table 3"

[ORCHESTRATOR] Phase 0: Target Acquisition
  → Flipper Zero on /dev/ttyACM0 ✓
  → BLE adapter (native) ✓
  → WiFi monitor mode ✗
  → Scope: BLE/WiFi/SubGHz within 10m
  → findings/target.json written

[ORCHESTRATOR] Phase 1: Reconnaissance → ralph_loop(bellum-recon, max=10)
  [RALPH ITER 1]
    bellum-recon: "Scanning all available protocols in parallel."
    ├── Task("BLE scan 15s") → 3 devices, QUADRUPED-XX at -42dBm
    ├── Task("nmap 192.168.4.0/24") → 1 host, ports 22/8080/9090
    └── Task("SubGHz scan 300-900MHz") → no signals
    bellum-recon: Wrote findings/surfaces.json (3 surfaces)
    bellum-recon: <promise>RECON_COMPLETE</promise>
  [RALPH] Gate passed: 3 surfaces found. Exiting loop.
  → Checkpoint: checkpoints/phase1.json

[ORCHESTRATOR] Phase 2: Research → ralph_loop(bellum-research, max=15)
  [RALPH ITER 1]
    bellum-research: "Researching 3 surfaces in parallel."
    ├── Task("Research BLE:QUADRUPED") → CVE found, existing Bleak PoC on GitHub
    ├── Task("Research HTTP:8080") → API docs found, no auth
    └── Task("Research SSH:22") → default creds common for this brand
    bellum-research: Wrote findings/intel.json (3 hypotheses)
    bellum-research: <promise>RESEARCH_COMPLETE</promise>
  [RALPH] Gate passed: 3 hypotheses. Exiting loop.
  → Checkpoint: checkpoints/phase2.json

[ORCHESTRATOR] Phase 3: Enumeration → ralph_loop(bellum-enumerate, max=10)
  [RALPH ITER 1]
    bellum-enumerate: "Deep-diving H1: BLE GATT write."
    → Bash: python3 scripts/hardware/ble_enumerate.py AA:BB:CC:DD:EE:FF
    → Found: service 0xFFE0, char 0xFFE1 (write, notify), no auth
    → Bash: python3 scripts/hardware/ble_read.py AA:BB:CC:DD:EE:FF 0xFFE1
    → Current value: 0x00 (idle)
    bellum-enumerate: H1 CONFIRMED. Exact params recorded.
  [RALPH ITER 2]
    bellum-enumerate: "Deep-diving H3: REST API."
    → Bash: curl http://192.168.4.1:8080/api/
    → Endpoint list, no auth. /api/cmd accepts POST.
    bellum-enumerate: H3 CONFIRMED. Wrote findings/vectors.json
    bellum-enumerate: <promise>ENUM_COMPLETE</promise>
  [RALPH] Gate passed: 2 confirmed vectors. Exiting loop.
  → Checkpoint: checkpoints/phase3.json

[ORCHESTRATOR] Phase 4: Exploitation → vector V1
  → ralph_loop(bellum-exploit, max=8, hitl_gate=true)
  [RALPH ITER 1]
    bellum-exploit: "Crafting BLE write payload for movement control."
    → WebSearch: "BLE GATT write movement command Bleak example"
    → Payload: 0x01 0x02 0x00 0x32 (move forward, speed 50)
    → Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 01020032
    *** HITL GATE: Approve BLE write to 0xFFE1 (move robot forward)? ***
    → USER: approved ✓
    → EXECUTED: robot moves forward!
    → Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 00000000
    *** HITL GATE: Approve BLE write to 0xFFE1 (emergency stop)? ***
    → USER: approved ✓
    → EXECUTED: robot stops.
    bellum-exploit: Wrote findings/exploit_V1.json
    bellum-exploit: <promise>EXPLOIT_COMPLETE</promise>
  [RALPH] Gate passed: impact confirmed. Exiting loop.
  → Checkpoint: checkpoints/phase4_V1.json

[ORCHESTRATOR] Phase 6: Report → ralph_loop(bellum-report, max=3)
  [RALPH ITER 1]
    bellum-report: Reading all findings...
    → Read: findings/target.json, surfaces.json, intel.json, vectors.json, exploit_V1.json
    → Writing comprehensive pentest report
    → Wrote reports/bellum-1709913600.md
    bellum-report: <promise>REPORT_COMPLETE</promise>
  [RALPH] Gate passed. Exiting loop.

[ORCHESTRATOR] ENGAGEMENT COMPLETE
  → Report: reports/bellum-1709913600.md
  → CRITICAL: Unauthenticated BLE command injection → full movement control
  → Total iterations: 7 (across 5 ralph loops)
  → Total subagent tasks: 9
  → Duration: 4m 32s
```

---

## File Layout (What We Ship)

```
bellum/                              # forked from opencode
├── packages/opencode/               # OpenCode source (forked)
│   └── src/bellum/                  # OUR ADDITIONS
│       ├── orchestrator.ts
│       ├── ralph.ts
│       ├── state.ts
│       ├── gates.ts
│       └── prompts/
├── scripts/                         # Python tools (called via Bash)
│   ├── hardware/
│   │   ├── ble_scan.py
│   │   ├── ble_enumerate.py
│   │   ├── ble_write.py
│   │   ├── subghz_scan.py
│   │   ├── subghz_replay.py
│   │   └── ...
│   ├── recon/
│   │   ├── cve_search.py
│   │   ├── shodan_search.py
│   │   ├── github_search.py
│   │   └── fcc_lookup.py
│   └── util/
│       ├── packet_analyze.py
│       └── firmware_analyze.py
├── .opencode/
│   ├── skills/                      # Attack workflow instructions
│   │   ├── ble-recon/SKILL.md
│   │   ├── ble-exploit/SKILL.md
│   │   ├── rf-replay/SKILL.md
│   │   └── ...
│   ├── plugins/                     # Hooks (HITL, recovery, audit)
│   │   ├── hitl-gate.ts
│   │   ├── hardware-recovery.ts
│   │   └── audit-log.ts
│   └── opencode.json               # MCP servers, model config
├── findings/                        # Runtime output (gitignored)
├── checkpoints/                     # Crash recovery (gitignored)
├── reports/                         # Generated reports
└── requirements.txt                 # Python deps (bleak, pyflipper, scapy, etc.)
```
