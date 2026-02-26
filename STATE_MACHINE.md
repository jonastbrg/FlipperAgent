# Bellum Agent State Machine v3

**Version:** 3.0
**Date:** 2026-02-26
**Architecture:** OpenCode fork + Ralph Wiggum loops + subagent orchestration + yolo mode

---

## What Changed from v2

v2 had HITL gates everywhere and treated subagents as an afterthought. v3 flips both:

| v2 | v3 |
|----|-----|
| HITL gates on all exploit tools | **Yolo mode by default.** Optional HITL for exploits only, toggled via env var. |
| Subagents mentioned but vague | **Concrete subagent spawn tree.** Every phase shows exactly which subagents run, in parallel or series, with what tools. |
| Sequential ralph loops | **Subagents ARE the ralph loops.** The orchestrator spawns phase agents as subagents. Each is a ralph loop. |
| LLM-managed pivot logic | **Orchestrator-managed pivot.** Deterministic for loop over vectors. |

---

## Yolo Mode

**Default: fully autonomous.** No approval prompts. The agent blasts through recon → research → enum → exploit → report without stopping.

**Config (`opencode.json`):**
```json
{
    "permissions": {
        "allow": [
            "Bash(*)", "Read(*)", "Write(*)", "Edit(*)",
            "Glob(*)", "Grep(*)", "WebSearch(*)", "WebFetch(*)",
            "Task(*)", "TodoWrite(*)"
        ]
    }
}
```

**Selective HITL (optional, for safety-conscious runs):**
```typescript
// .opencode/plugins/exploit-gate.ts
export default {
    name: "exploit-gate",
    hooks: {
        "permission.ask": async (ctx) => {
            const dangerous = ["ble_write", "subghz_replay", "ir_replay", "badusb"];
            const cmd = ctx.tool?.input?.command || "";
            if (process.env.BELLUM_HITL === "true" &&
                dangerous.some(d => cmd.includes(d))) {
                return { action: "ask" };
            }
            return { action: "allow" };
        }
    }
};
```

**Running:**
```bash
# Full yolo — zero interaction, full autonomous attack chain
bellum "Attack that quadruped robot"

# Autonomous everything, pause only before sending payloads to hardware
BELLUM_HITL=true bellum "Attack that quadruped robot"
```

Subagents **inherit parent permissions**, so yolo propagates to every subagent in the tree.

---

## High-Level Architecture

```
$ bellum "Attack that quadruped robot on table 3"
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     BELLUM ORCHESTRATOR                                │
│            (deterministic TypeScript — our fork code)                  │
│                                                                        │
│  1. acquire_target()           ← no LLM, just hardware checks         │
│  2. spawn bellum-recon         ← ralph loop subagent (yolo)            │
│  3. validate surfaces.json    ← backpressure gate                      │
│  4. spawn bellum-research      ← ralph loop subagent (yolo)            │
│  5. validate intel.json       ← backpressure gate                      │
│  6. spawn bellum-enumerate     ← ralph loop subagent (yolo)            │
│  7. validate vectors.json     ← backpressure gate                      │
│  8. for vector in vectors:    ← deterministic pivot loop               │
│       spawn bellum-exploit     ← ralph loop subagent (yolo or HITL)    │
│       if success: break                                                │
│  9. spawn bellum-report        ← ralph loop subagent (yolo)            │
│ 10. done                                                               │
│                                                                        │
│  RECOVERY: plugin hooks intercept hardware failures inline             │
└────────────────────────────────────────────────────────────────────────┘
```

The orchestrator is **~100 lines of deterministic TypeScript**. It has no LLM calls. It just:
1. Spawns phase agents as subagents (each is a ralph loop)
2. Reads their output files
3. Validates via backpressure gates
4. Decides the next phase (or pivot)

---

## Subagent Spawn Tree

This is the complete hierarchy. Every box is a separate agent with its own context window.

```
ORCHESTRATOR (TypeScript, no LLM)
│
├── bellum-recon (ralph loop, yolo, fast model)
│   │
│   │   The recon agent's job: discover attack surfaces.
│   │   It reads findings/target.json, runs scans, writes findings/surfaces.json.
│   │
│   ├── Task("BLE scan for 15 seconds")          ─── parallel ───┐
│   │   └── Bash: python3 scripts/hardware/ble_scan.py --dur 15  │
│   │                                                              │
│   ├── Task("nmap service scan 192.168.0.0/24")  ─── parallel ──┤
│   │   └── Bash: nmap -sV -T4 192.168.0.0/24 -oJ /tmp/nmap.json│
│   │                                                              │
│   ├── Task("SubGHz scan 300-900MHz for 20s")     ─── parallel ──┤
│   │   └── Bash: python3 scripts/hardware/subghz_scan.py         │
│   │                                                              │
│   └── Task("WiFi scan nearby networks")          ─── parallel ──┘
│       └── Bash: python3 scripts/hardware/wifi_scan.py
│
│   All 4 return results → recon agent merges → writes surfaces.json
│   Ralph loop checks: does surfaces.json have >= 1 surface?
│   YES → exit loop, return to orchestrator
│   NO  → re-iterate (try different scan params, longer duration, etc.)
│
├── bellum-research (ralph loop, yolo, strong reasoning model)
│   │
│   │   The research agent's job: OSINT enrichment.
│   │   It reads surfaces.json, researches each surface, writes intel.json.
│   │
│   ├── Task("Research BLE surface: QUADRUPED-XX")  ─── parallel ──┐
│   │   ├── WebSearch: "QUADRUPED robot BLE vulnerability 2025"     │
│   │   ├── WebFetch: (CVE detail page)                             │
│   │   ├── Bash: python3 scripts/recon/github_search.py "QUADRUPED BLE exploit"
│   │   └── Bash: python3 scripts/recon/cve_search.py "QUADRUPED"  │
│   │                                                                │
│   ├── Task("Research HTTP surface: 192.168.4.1:8080") ── parallel ┤
│   │   ├── WebSearch: "QUADRUPED robot web API documentation"       │
│   │   ├── Bash: python3 scripts/recon/shodan_search.py "QUADRUPED"│
│   │   └── WebFetch: (API docs page)                               │
│   │                                                                │
│   └── Task("Research SSH surface: 192.168.4.1:22")  ─── parallel ─┘
│       ├── WebSearch: "QUADRUPED robot default SSH credentials"
│       └── Bash: python3 scripts/recon/cve_search.py "OpenSSH 8.9"
│
│   All 3 return intel → research agent merges → writes intel.json
│   Ralph loop checks: does intel.json have >= 1 hypothesis?
│   YES → exit loop
│   NO  → re-iterate (broader search terms, different databases)
│
├── bellum-enumerate (ralph loop, yolo, strong model)
│   │
│   │   The enumeration agent's job: confirm hypotheses, extract attack params.
│   │   It reads surfaces.json + intel.json, probes target, writes vectors.json.
│   │
│   │   (Runs hypotheses in priority order, NOT parallel — interacting with
│   │    the same target device simultaneously could cause BLE conflicts)
│   │
│   ├── Hypothesis H1: BLE GATT write
│   │   ├── Bash: python3 scripts/hardware/ble_enumerate.py AA:BB:CC:DD:EE:FF
│   │   ├── Bash: python3 scripts/hardware/ble_read.py AA:BB:CC:DD:EE:FF 0xFFE1
│   │   └── Result: CONFIRMED — char 0xFFE1 writable, no auth
│   │
│   ├── Hypothesis H3: REST API injection
│   │   ├── Bash: curl -s http://192.168.4.1:8080/api/ | python3 -m json.tool
│   │   ├── Bash: curl -s http://192.168.4.1:8080/api/status
│   │   └── Result: CONFIRMED — /api/cmd accepts POST, no auth
│   │
│   └── writes vectors.json with confirmed vectors, ranked
│
│   Ralph loop checks: does vectors.json have >= 1 confirmed vector?
│   YES → exit loop
│   NO  → re-iterate (try different enumeration approaches)
│
├── FOR vector IN vectors.json:    ← deterministic pivot loop (orchestrator code)
│   │
│   └── bellum-exploit (ralph loop, yolo or HITL, strongest model)
│       │
│       │   The exploit agent's job: craft and execute PoC.
│       │   It reads vectors.json + intel.json, develops exploit, executes it.
│       │
│       │   Iteration 1:
│       ├── WebSearch: "BLE GATT write movement command Bleak example"
│       ├── Bash: python3 -c "# craft payload based on research..."
│       ├── Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 01020032
│       │         ↑ If BELLUM_HITL=true, plugin intercepts and prompts user
│       │         ↑ If BELLUM_HITL=false (default), auto-approved, fires immediately
│       ├── Result: robot moves → SUCCESS
│       └── writes findings/exploit_V1.json
│
│       Ralph loop checks: does exploit_V1.json have non-null "impact"?
│       YES → exit loop, return success to orchestrator
│       NO  → re-iterate (different payload, different approach)
│       Max iterations exhausted → return failure, orchestrator tries next vector
│
│   Orchestrator: exploit succeeded? → break out of for loop
│   Orchestrator: exploit failed? → continue to next vector (PIVOT)
│   Orchestrator: all vectors failed? → proceed to report anyway
│
└── bellum-report (ralph loop, yolo, fast model)
    │
    │   The report agent's job: generate pentest report.
    │   It reads ALL files in findings/, writes reports/bellum-{id}.md.
    │
    ├── Read: findings/target.json
    ├── Read: findings/surfaces.json
    ├── Read: findings/intel.json
    ├── Read: findings/vectors.json
    ├── Read: findings/exploit_V1.json (and any others)
    └── Write: reports/bellum-{engagement_id}.md

    Ralph loop checks: does report file exist AND have all required sections?
    YES → exit loop
    NO  → re-iterate
```

---

## Agent Definitions

Each phase agent is defined as a custom OpenCode agent. These live in `.opencode/agents/` and specify model, tool access, and system prompt.

### bellum-recon

```yaml
# .opencode/agents/bellum-recon.md frontmatter
name: bellum-recon
description: Cyber-physical reconnaissance agent — discovers attack surfaces
model: kimi/k2.5          # fast, good tool calling, cheap
tools:
  - Bash
  - Task                   # can spawn parallel scan subagents
  - Read
  - Write
  - Glob
  - TodoWrite
```

**System prompt (body of the .md file):**
```
You are a reconnaissance agent for an autonomous cyber-physical security evaluation.

Read findings/target.json for the target specification and available hardware.
Read findings/surfaces.json if it exists (you may be continuing from a previous iteration).

Your mission: discover ALL wireless and network attack surfaces the target exposes.

STRATEGY:
1. Launch parallel scans using Task tool — one per protocol:
   - BLE: `python3 scripts/hardware/ble_scan.py --duration 15`
   - nmap: `nmap -sV -T4 {target_ip_range} -oJ /tmp/nmap.json`
   - SubGHz: `python3 scripts/hardware/subghz_scan.py --range 300-900 --duration 20`
   - WiFi: `python3 scripts/hardware/wifi_scan.py`
2. Merge all results into findings/surfaces.json
3. Each surface needs: protocol, identifier, signal_strength/port, details

Only use tools that match available hardware (check findings/target.json).

When findings/surfaces.json is complete, output <promise>RECON_COMPLETE</promise>
```

### bellum-research

```yaml
name: bellum-research
description: OSINT and vulnerability research agent
model: anthropic/claude-sonnet  # strong reasoning for research synthesis
tools:
  - Bash                   # for cve_search.py, shodan_search.py, github_search.py
  - Task                   # parallel research per surface
  - WebSearch              # direct OSINT
  - WebFetch               # read vuln pages, docs, teardowns
  - Read
  - Write
  - TodoWrite
```

**System prompt:**
```
You are a vulnerability researcher for an autonomous cyber-physical security evaluation.

Read findings/surfaces.json for discovered attack surfaces.
Read findings/intel.json if it exists (continuing from previous iteration).

Your mission: for each surface, find known vulnerabilities, existing exploits,
documentation, and teardowns. Form ranked attack hypotheses.

STRATEGY:
1. Launch parallel research using Task tool — one subagent per surface:
   - Each subagent should: WebSearch for vulns, run cve_search.py, run github_search.py,
     run shodan_search.py (if IP-based surface), WebFetch relevant pages
2. Merge all research into findings/intel.json
3. Rank hypotheses by likelihood of exploitation success

When findings/intel.json is complete with ranked hypotheses,
output <promise>RESEARCH_COMPLETE</promise>
```

### bellum-enumerate

```yaml
name: bellum-enumerate
description: Deep enumeration agent — confirms hypotheses, extracts attack params
model: anthropic/claude-sonnet  # needs to reason about protocols
tools:
  - Bash                   # for ble_enumerate.py, ble_read.py, curl, ssh
  - Read
  - Write
  - WebSearch              # for protocol documentation
  - WebFetch
  - TodoWrite
  # NOTE: no Task tool — enumeration is sequential per hypothesis
  # to avoid BLE/hardware conflicts from parallel connections
```

**System prompt:**
```
You are an enumeration specialist for an autonomous cyber-physical security evaluation.

Read findings/surfaces.json, findings/intel.json, and findings/vectors.json (if exists).

Your mission: test each hypothesis from intel.json against the actual target.
Confirm or reject. For confirmed hypotheses, extract EXACT attack parameters.

PROCESS (sequential, NOT parallel — avoid hardware conflicts):
1. Take the highest-ranked untested hypothesis
2. Interact with the target surface (BLE enumerate, HTTP probe, SSH attempt, etc.)
3. Confirm or reject the hypothesis
4. If confirmed: record exact parameters (UUIDs, endpoints, payload format, etc.)
5. If rejected: record why
6. Move to next hypothesis

Write results to findings/vectors.json.

When all hypotheses are tested, output <promise>ENUM_COMPLETE</promise>
```

### bellum-exploit

```yaml
name: bellum-exploit
description: Exploit development and execution agent
model: anthropic/claude-sonnet  # strongest reasoning for exploit crafting
tools:
  - Bash                   # for ble_write.py, subghz_replay.py, curl, custom scripts
  - Read
  - Write
  - WebSearch              # for reference exploit code
  - WebFetch
  - TodoWrite
```

**System prompt:**
```
You are an exploit developer for an autonomous cyber-physical security evaluation.

Read findings/vectors.json for the confirmed attack vector you are targeting.
Read findings/intel.json for supporting research.
Read findings/exploit_{vector_id}.json if it exists (continuing from previous iteration).

Your mission: craft and execute a proof-of-concept exploit that demonstrates
real-world impact on the target.

PROCESS:
1. Study the vector parameters and research intel
2. Search for reference exploit code if needed (WebSearch)
3. Craft the exploit payload
4. Execute it via the appropriate tool:
   - BLE: python3 scripts/hardware/ble_write.py {mac} {char_uuid} {payload}
   - SubGHz: python3 scripts/hardware/subghz_replay.py {capture_file}
   - HTTP: curl -X POST {endpoint} -d '{payload}'
   - SSH: python3 scripts/hardware/ssh_connect.py {host} {user} {pass}
5. Observe the result — did the target respond? Was there visible impact?
6. Document everything in findings/exploit_{vector_id}.json
7. If first attempt failed: analyze why, adjust payload, try again

Write results to findings/exploit_{vector_id}.json including:
- payload_sent, result, impact (describe physical/observable effect), evidence

When you have demonstrated impact OR exhausted approaches,
output <promise>EXPLOIT_COMPLETE</promise>
```

### bellum-report

```yaml
name: bellum-report
description: Pentest report generation agent
model: kimi/k2.5          # fast, just needs to write well
tools:
  - Read                   # read all findings
  - Write                  # write report
  - Glob                   # find all findings files
  - TodoWrite
  # NOTE: no Bash, no WebSearch, no hardware tools — report only
```

**System prompt:**
```
You are a penetration test report writer.

Read ALL files in the findings/ directory:
- findings/target.json
- findings/surfaces.json
- findings/intel.json
- findings/vectors.json
- findings/exploit_*.json

Generate a professional adversarial evaluation report.

{report_template}

Write to reports/bellum-{engagement_id}.md.

When the report is complete, output <promise>REPORT_COMPLETE</promise>
```

---

## The Orchestrator (Our Fork Code)

```typescript
// packages/opencode/src/bellum/orchestrator.ts

import { spawnAgent, readJson, writeJson, checkHardware } from "./util";
import { validateSurfaces, validateIntel, validateVectors, validateExploit, validateReport } from "./gates";

interface BellumConfig {
    target: string;
    maxReconIter: number;     // default 10
    maxResearchIter: number;  // default 15
    maxEnumIter: number;      // default 10
    maxExploitIter: number;   // default 8
    maxReportIter: number;    // default 3
    hitl: boolean;            // default false (yolo)
}

export async function runEngagement(config: BellumConfig) {
    const engagementId = `bellum-${Date.now()}`;

    // PHASE 0: Target acquisition (no LLM)
    const hardware = await checkHardware();
    await writeJson("findings/target.json", {
        engagement_id: engagementId,
        target: config.target,
        hardware,
        available_tools: deriveToolset(hardware),
    });

    // PHASE 1: Recon
    await spawnAgent({
        agent: "bellum-recon",
        maxIterations: config.maxReconIter,
        completionPromise: "RECON_COMPLETE",
    });
    if (!validateSurfaces("findings/surfaces.json")) {
        return await runReport(engagementId, "No attack surfaces discovered");
    }

    // PHASE 2: Research
    await spawnAgent({
        agent: "bellum-research",
        maxIterations: config.maxResearchIter,
        completionPromise: "RESEARCH_COMPLETE",
    });
    if (!validateIntel("findings/intel.json")) {
        return await runReport(engagementId, "No attack hypotheses formed");
    }

    // PHASE 3: Enumeration
    await spawnAgent({
        agent: "bellum-enumerate",
        maxIterations: config.maxEnumIter,
        completionPromise: "ENUM_COMPLETE",
    });
    if (!validateVectors("findings/vectors.json")) {
        return await runReport(engagementId, "No exploitable vectors confirmed");
    }

    // PHASE 4+5: Exploit + Pivot
    const vectors = await readJson("findings/vectors.json");
    let exploitSuccess = false;

    for (const vector of vectors.vector_priority) {
        await spawnAgent({
            agent: "bellum-exploit",
            maxIterations: config.maxExploitIter,
            completionPromise: "EXPLOIT_COMPLETE",
            env: { CURRENT_VECTOR: vector, BELLUM_HITL: String(config.hitl) },
        });

        if (validateExploit(`findings/exploit_${vector}.json`)) {
            exploitSuccess = true;
            break;  // THE PIVOT: for loop IS the pivot logic
        }
        // else: continue to next vector automatically
    }

    // PHASE 6: Report
    await runReport(engagementId, exploitSuccess ? "Exploitation successful" : "All vectors attempted");
}

async function runReport(engagementId: string, summary: string) {
    await writeJson("findings/summary.json", { engagementId, summary });
    await spawnAgent({
        agent: "bellum-report",
        maxIterations: 3,
        completionPromise: "REPORT_COMPLETE",
    });
}
```

**That's it.** ~80 lines. The orchestrator:
1. Checks hardware (deterministic)
2. Spawns phase agents in sequence (each is a ralph loop)
3. Validates output between phases (backpressure gates)
4. Loops over vectors for exploit/pivot (deterministic for loop)
5. Always generates a report, even on partial completion

---

## Backpressure Gates

Simple validation functions. No LLM involved.

```typescript
// packages/opencode/src/bellum/gates.ts

export function validateSurfaces(path: string): boolean {
    const data = readJsonSync(path);
    return data?.surfaces?.length >= 1;
}

export function validateIntel(path: string): boolean {
    const data = readJsonSync(path);
    return data?.hypotheses?.length >= 1;
}

export function validateVectors(path: string): boolean {
    const data = readJsonSync(path);
    return data?.vectors?.some((v: any) => v.confirmed === true);
}

export function validateExploit(path: string): boolean {
    const data = readJsonSync(path);
    return data?.impact != null && data?.success === true;
}

export function validateReport(path: string): boolean {
    const content = readFileSync(path, "utf-8");
    return content.includes("## Executive Summary") &&
           content.includes("## Findings") &&
           content.includes("## Recommendations");
}
```

---

## Recovery (Plugin Hooks, Not a Phase)

Recovery is NOT a state. It's **inline plugin hooks** that fire when tools fail.

```typescript
// .opencode/plugins/hardware-recovery.ts
export default {
    name: "hardware-recovery",
    hooks: {
        "tool.execute.after": async (ctx) => {
            const err = ctx.result?.stderr || "";

            // Serial disconnection
            if (err.includes("SerialException") || err.includes("could not open port")) {
                console.log("[RECOVERY] Flipper disconnected. Attempting reconnection...");
                const reconnected = await retry(() =>
                    exec("python3 scripts/hardware/flipper_serial.py --ping"),
                    { attempts: 3, backoff: 2000 }
                );
                if (!reconnected) {
                    // Update hardware status so agent knows to skip Flipper tools
                    await writeJson("findings/hardware_status.json", {
                        flipper: "disconnected",
                        timestamp: Date.now()
                    });
                }
            }

            // BLE connection failure
            if (err.includes("BleakError") || err.includes("ConnectionError")) {
                console.log("[RECOVERY] BLE connection failed. Retrying...");
                await exec("sudo hciconfig hci0 reset");
            }
        }
    }
};
```

```typescript
// .opencode/plugins/stuck-detection.ts
let lastToolCall = "";
let repeatCount = 0;

export default {
    name: "stuck-detection",
    hooks: {
        "tool.execute.before": async (ctx) => {
            const sig = JSON.stringify({ tool: ctx.tool.name, input: ctx.tool.input });
            if (sig === lastToolCall) {
                repeatCount++;
                if (repeatCount >= 3) {
                    // Force the agent to try something different
                    return {
                        action: "modify",
                        message: "WARNING: You have repeated the same tool call 3 times. " +
                                "Try a DIFFERENT approach or output your completion promise."
                    };
                }
            } else {
                lastToolCall = sig;
                repeatCount = 0;
            }
        }
    }
};
```

```typescript
// .opencode/plugins/audit-log.ts
export default {
    name: "audit-log",
    hooks: {
        "tool.execute.before": async (ctx) => {
            const entry = {
                timestamp: new Date().toISOString(),
                agent: ctx.agent?.name,
                tool: ctx.tool.name,
                input: ctx.tool.input,
            };
            appendFileSync("findings/audit_log.jsonl", JSON.stringify(entry) + "\n");
        },
        "tool.execute.after": async (ctx) => {
            const entry = {
                timestamp: new Date().toISOString(),
                agent: ctx.agent?.name,
                tool: ctx.tool.name,
                success: !ctx.result?.error,
                output_preview: (ctx.result?.stdout || "").slice(0, 200),
            };
            appendFileSync("findings/audit_log.jsonl", JSON.stringify(entry) + "\n");
        }
    }
};
```

---

## Context Window Strategy

**Ralph loops solve context blowout.** Each iteration starts with a fresh context window. The agent reads its own previous work from files.

But within a single iteration, an agent might make many tool calls. Here's how we manage it:

| Tool | Typical Output Size | Strategy |
|------|-------------------|----------|
| ble_scan.py | ~500 tokens | Fine as-is |
| nmap (full /24) | ~3000 tokens | Script outputs JSON summary, not raw nmap |
| WebSearch | ~1000 tokens | Fine as-is |
| WebFetch | ~3000 tokens | Agent reads via WebFetch which already truncates |
| ble_enumerate.py | ~1500 tokens | Script outputs structured JSON only |
| packet_analyze.py | ~2000 tokens | Script outputs summary, not raw pcap |

**Key rule:** All Python scripts in `scripts/` output **structured JSON summaries**, not raw tool output. The script does the parsing; the LLM gets clean data.

```python
# Example: scripts/hardware/ble_scan.py outputs:
{
    "scan_duration": 15,
    "devices_found": 3,
    "devices": [
        {"name": "QUADRUPED-XX", "mac": "AA:BB:CC:DD:EE:FF", "rssi": -42, "connectable": true},
        {"name": "Unknown", "mac": "11:22:33:44:55:66", "rssi": -78, "connectable": false},
        {"name": "SmartBulb", "mac": "77:88:99:AA:BB:CC", "rssi": -65, "connectable": true}
    ]
}
# NOT raw Bleak output with hex dumps and advertisement data
```

Between ralph loop iterations, the agent's previous context is discarded. It reads from `findings/*.json` to pick up where it left off. This means:
- **Iteration 1:** 0 tokens of history. Runs scans, writes findings.
- **Iteration 2:** 0 tokens of history. Reads findings from disk. Sees what's missing. Fills gaps.
- **Iteration 3:** 0 tokens of history. Reads findings from disk. Everything complete. Outputs promise.

Effective context per iteration: ~10K tokens (prompt + tool outputs). Max context never exceeded.

---

## Example Trace (v3 — yolo mode, full auto)

```
$ bellum "Attack that quadruped robot on table 3"

[ORCHESTRATOR] Phase 0: Target Acquisition
  Hardware: Flipper ✓ | BLE ✓ | WiFi (no monitor) ✗
  → findings/target.json

[ORCHESTRATOR] Phase 1: Recon → spawning bellum-recon
  [RALPH bellum-recon ITER 1]
    "Launching parallel scans."
    ├── Task("BLE scan 15s")    → 3 devices found
    ├── Task("nmap 192.168.4.0/24") → 1 host, ports 22/8080/9090
    ├── Task("SubGHz 300-900MHz")   → no signals
    └── Task("WiFi scan")          → "RobotAP-5G" found
    Merged → findings/surfaces.json (3 surfaces)
    <promise>RECON_COMPLETE</promise>
  [GATE] surfaces.json: 3 surfaces ✓

[ORCHESTRATOR] Phase 2: Research → spawning bellum-research
  [RALPH bellum-research ITER 1]
    "Researching 3 surfaces in parallel."
    ├── Task("Research BLE:QUADRUPED-XX")
    │   └── WebSearch + cve_search + github_search → CVE found, PoC on GitHub
    ├── Task("Research HTTP:192.168.4.1:8080")
    │   └── WebSearch + shodan + WebFetch → API docs, no auth
    └── Task("Research SSH:192.168.4.1:22")
        └── WebSearch + cve_search → default creds common
    Merged → findings/intel.json (3 hypotheses, ranked [H1, H3, H2])
    <promise>RESEARCH_COMPLETE</promise>
  [GATE] intel.json: 3 hypotheses ✓

[ORCHESTRATOR] Phase 3: Enumeration → spawning bellum-enumerate
  [RALPH bellum-enumerate ITER 1]
    Testing H1: BLE GATT write
    → Bash: python3 scripts/hardware/ble_enumerate.py AA:BB:CC:DD:EE:FF
    → Char 0xFFE1: writable, no auth required
    → CONFIRMED ✓
    Testing H3: REST API
    → Bash: curl -s http://192.168.4.1:8080/api/cmd -X POST -d '{"test":true}'
    → 200 OK, command accepted
    → CONFIRMED ✓
    → findings/vectors.json (V1: BLE write, V2: REST API)
    <promise>ENUM_COMPLETE</promise>
  [GATE] vectors.json: 2 confirmed vectors ✓

[ORCHESTRATOR] Phase 4: Exploit → vector V1 (BLE write)
  [RALPH bellum-exploit ITER 1]
    Crafting BLE payload for movement control.
    → WebSearch: "BLE GATT write Bleak movement command"
    → Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 01020032
      ↑ YOLO: auto-approved, fires immediately
    → Robot moves forward ✓
    → Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 00000000
    → Robot stops ✓
    → findings/exploit_V1.json (impact: "full movement control")
    <promise>EXPLOIT_COMPLETE</promise>
  [GATE] exploit_V1.json: impact confirmed ✓
  [ORCHESTRATOR] Exploit succeeded → skip remaining vectors

[ORCHESTRATOR] Phase 6: Report → spawning bellum-report
  [RALPH bellum-report ITER 1]
    Reading all findings...
    → reports/bellum-1709913600.md
    <promise>REPORT_COMPLETE</promise>

[ORCHESTRATOR] ENGAGEMENT COMPLETE
  Report: reports/bellum-1709913600.md
  CRITICAL: Unauthenticated BLE command injection → full movement control
  Ralph loop iterations: 5 (across 5 phases)
  Subagent tasks spawned: 11
  Total time: 3m 47s
  Human interactions: 0 (yolo mode)
```

---

## File Layout

```
bellum/                                    # forked from opencode
├── packages/opencode/                     # OpenCode source (forked, MIT)
│   └── src/bellum/                        # OUR ADDITIONS
│       ├── orchestrator.ts                # ~80 LOC: phase sequencing
│       ├── ralph.ts                       # ~60 LOC: ralph loop implementation
│       ├── gates.ts                       # ~40 LOC: backpressure validators
│       ├── util.ts                        # ~30 LOC: helpers
│       └── cli.ts                         # ~20 LOC: `bellum` CLI entry point
│                                          # TOTAL: ~230 LOC TypeScript
├── scripts/                               # Python tools (called via Bash)
│   ├── hardware/
│   │   ├── ble_scan.py                    # Bleak scan → JSON
│   │   ├── ble_enumerate.py               # Bleak GATT enum → JSON
│   │   ├── ble_read.py                    # Bleak read char → JSON
│   │   ├── ble_write.py                   # Bleak write char (the exploit tool)
│   │   ├── ble_subscribe.py               # Bleak notifications → JSON stream
│   │   ├── subghz_scan.py                 # pyFlipper Sub-GHz scan → JSON
│   │   ├── subghz_capture.py              # pyFlipper capture → .sub file
│   │   ├── subghz_replay.py               # pyFlipper replay .sub file
│   │   ├── ir_capture.py                  # pyFlipper IR capture → JSON
│   │   ├── ir_replay.py                   # pyFlipper IR replay
│   │   ├── wifi_scan.py                   # scapy/iwlist → JSON
│   │   └── flipper_serial.py              # pyFlipper generic serial interface
│   ├── recon/
│   │   ├── cve_search.py                  # NVD API → JSON
│   │   ├── shodan_search.py               # Shodan API → JSON
│   │   ├── github_search.py               # GitHub API → JSON
│   │   └── fcc_lookup.py                  # FCC API → JSON
│   └── util/
│       ├── packet_analyze.py              # pyshark → JSON summary
│       └── firmware_analyze.py            # binwalk → JSON summary
├── .opencode/
│   ├── agents/                            # Phase agent definitions
│   │   ├── bellum-recon.md
│   │   ├── bellum-research.md
│   │   ├── bellum-enumerate.md
│   │   ├── bellum-exploit.md
│   │   └── bellum-report.md
│   ├── skills/                            # Attack workflow instructions
│   │   ├── ble-recon/SKILL.md
│   │   ├── ble-exploit/SKILL.md
│   │   ├── rf-replay/SKILL.md
│   │   ├── network-recon/SKILL.md
│   │   └── osint/SKILL.md
│   ├── plugins/                           # Runtime hooks
│   │   ├── exploit-gate.ts                # Optional HITL for exploit tools
│   │   ├── hardware-recovery.ts           # Auto-reconnect on hardware failures
│   │   ├── stuck-detection.ts             # Catch repeated identical tool calls
│   │   └── audit-log.ts                   # Log every tool call for report
│   └── opencode.json                      # Permissions (yolo), MCP servers
├── findings/                              # Runtime output (gitignored)
│   ├── target.json
│   ├── surfaces.json
│   ├── intel.json
│   ├── vectors.json
│   ├── exploit_V1.json
│   ├── hardware_status.json
│   └── audit_log.jsonl
├── reports/                               # Generated pentest reports
└── requirements.txt                       # Python: bleak, pyflipper, scapy, shodan, etc.
```

---

## Summary: What Makes v3 Different

| Aspect | v1 | v2 | v3 |
|--------|-----|-----|-----|
| **State management** | LLM (fragile) | Orchestrator + ralph loops | Orchestrator + ralph loops |
| **HITL** | Everywhere | Exploit phase only | **Yolo default, optional HITL** |
| **Subagents** | Not specified | Mentioned | **Full spawn tree with tool access** |
| **Agent definitions** | Vague | Described | **Complete .md files with prompts** |
| **Parallelism** | None | Within-phase | **Concrete: 4 parallel recon scans, 3 parallel research tasks** |
| **Orchestrator** | N/A | Pseudocode | **Real TypeScript, ~230 LOC** |
| **Tool architecture** | Custom OpenCode tools | Python via Bash | **Python via Bash + built-in OpenCode tools** |
| **Recovery** | State in FSM | Plugin hooks | **Plugin hooks with concrete implementations** |
| **Context strategy** | Compression rules | Ralph loops | **Ralph loops + JSON-only script output** |
| **Demo readiness** | Theoretical | Plausible | **`bellum "prompt"` → autonomous attack → report** |
