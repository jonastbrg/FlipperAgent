# Bellum Agent State Machine v3.1

**Version:** 3.1
**Date:** 2026-02-26
**Architecture:** OpenCode fork + Ralph Wiggum loops + subagent orchestration + yolo mode

---

## What Changed from v3

v3 assumed OpenCode's subagent system works as documented. It doesn't. Deep research revealed three critical bugs that our fork MUST fix:

| Bug | Impact | OpenCode Issue | Our Fork Fix |
|-----|--------|----------------|--------------|
| **Subagents don't inherit parent permissions** | Subagents block indefinitely on permission prompts in unattended mode. Yolo on parent ≠ yolo on child. | [#12566](https://github.com/anomalyco/opencode/issues/12566) | Propagate parent `permission` config to child session in `task.ts` |
| **Subagents can't spawn subagents** | `task: false` hardcoded for all subagent sessions. Kills nested delegation. | [#7296](https://github.com/anomalyco/opencode/issues/7296) | Make `task` permission configurable per-agent. Add `task_depth` limit (default 2). |
| **No async task dispatch** | All subagents are synchronous/blocking. No fire-and-forget. | [#15069](https://github.com/anomalyco/opencode/issues/15069) | Add `Task.dispatch()` with async polling. (Stretch goal — sequential works for hackathon.) |

v3.1 also corrects the yolo mode configuration (v3 used wrong config keys).

---

## Yolo Mode (How It Actually Works)

Three layers, all needed for true autonomous operation:

### Layer 1: Non-Interactive Mode (`-p` flag)

```bash
# This is the real yolo — -p mode auto-approves ALL permissions
opencode -p "Attack that quadruped robot"
```

In `-p` (non-interactive) mode, **all permissions are auto-approved for the entire session**, including subagents. No user prompt ever appears. This is the closest equivalent to Claude Code's `--dangerously-skip-permissions`.

### Layer 2: Config-Based Permission Bypass

```json
// opencode.json — global allow-all
{
    "$schema": "https://opencode.ai/config.json",
    "permission": {
        "*": "allow"
    }
}
```

Granular version — allow everything but block truly dangerous patterns:
```json
{
    "permission": {
        "*": "allow",
        "bash": {
            "*": "allow",
            "rm -rf /": "deny",
            "dd if=*": "deny"
        }
    }
}
```

### Layer 3: Plugin-Based Auto-Approve

```typescript
// .opencode/plugins/yolo.ts
import type { Plugin } from "@opencode-ai/plugin"

export const YoloPlugin: Plugin = async (ctx) => {
    return {
        'permission.ask': async (permission, output) => {
            // Auto-approve everything
            output.status = 'allow'
        },
    }
}
```

Selective version — yolo for everything except exploit execution:
```typescript
// .opencode/plugins/exploit-gate.ts
export const ExploitGate: Plugin = async (ctx) => {
    return {
        'permission.ask': async (permission, output) => {
            if (process.env.BELLUM_HITL === "true") {
                const cmd = String(permission.meta?.command || "");
                const dangerous = ["ble_write", "subghz_replay", "ir_replay", "badusb"];
                if (dangerous.some(d => cmd.includes(d))) {
                    return; // fall through to normal prompt
                }
            }
            output.status = 'allow';
        },
    }
}
```

### Running Bellum

```bash
# Full yolo — -p mode auto-approves everything, including subagents
opencode -p "Attack that quadruped robot on table 3"

# With our CLI wrapper (calls opencode -p under the hood):
bellum "Attack that quadruped robot on table 3"

# Yolo everything except exploit execution (prompts before sending payloads):
BELLUM_HITL=true bellum "Attack that quadruped robot"

# Restrict available tools:
bellum "Attack that quadruped" --excludedTools=badusb
```

### Permission Inheritance Fix (Our Fork)

Upstream bug: child sessions in `task.ts` (lines ~72-101) only get hardcoded deny rules. They never inherit parent permission config.

**Our fix in the fork:**
```typescript
// packages/opencode/src/session/task.ts — our modification
const childSession = await createSession({
    agent: subagentName,
    parent: parentSession.id,
    // FIX: propagate parent permission config to child
    permission: parentSession.agent.permission ?? parentSession.config.permission,
    // FIX: allow nested task delegation (with depth limit)
    taskEnabled: (parentSession.taskDepth ?? 0) < MAX_TASK_DEPTH,
    taskDepth: (parentSession.taskDepth ?? 0) + 1,
});
```

This is a ~10 line change in the fork. Without it, subagents in yolo mode block forever.

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

### OpenCode Subagent Reality Check

Before the spawn tree, the constraints we're working with (discovered via deep research on upstream issues):

| Constraint | Upstream Issue | Impact | Our Fix |
|------------|----------------|--------|---------|
| **Subagents don't inherit permissions** | [#12566](https://github.com/anomalyco/opencode/issues/12566) | Subagents block on permission prompts forever in unattended mode | `opencode -p` auto-approves all + global `"*": "allow"` config (belt and suspenders) |
| **Subagents can't spawn subagents** | [#7296](https://github.com/anomalyco/opencode/issues/7296) | `task: false` hardcoded in `task.ts`. No nested delegation. | Fork fix: make `task` configurable per-agent with `task_depth` limit. |
| **Plan mode bypassed by subagents** | [#6527](https://github.com/anomalyco/opencode/issues/6527) | Subagents run with full permissions even if parent is restricted. Actually helps us — but indicates permission model is buggy. | Aware of it, leverage it. |
| **No async task dispatch** | [#15069](https://github.com/anomalyco/opencode/issues/15069) | All Task calls synchronous. Parallel = multiple Tasks in one LLM message. | Fine for hackathon. Fork fix later. |

**Critical architecture decision: each phase agent runs as a top-level `opencode -p` invocation, NOT as a nested subagent.** The orchestrator is a shell script / TS process that calls `opencode -p` for each phase. This sidesteps all three bugs:

1. `-p` mode auto-approves permissions (no inheritance needed)
2. Each phase agent is depth 0, its Task subagents are depth 1 (no depth-2 nesting needed)
3. Parallel tasks within a phase work natively (multiple Task calls in one message)

**Fork fix still needed for:** making depth-1 subagents respect the global `"*": "allow"` config. Without this, Task subagents spawned by the phase agent may still prompt. Belt-and-suspenders: the `permission.ask` plugin also auto-approves.

### The Complete Hierarchy

Every box is a separate agent with its own context window.

```
ORCHESTRATOR (TypeScript process, no LLM — calls opencode -p for each phase)
│
│   Each phase = a fresh `opencode -p` invocation (depth 0, auto-approved).
│   Within each phase, the LLM can spawn Task subagents (depth 1).
│   This avoids all three upstream subagent bugs.
│
├─── opencode -p --agent bellum-recon [prompt]          ← DEPTH 0 (fresh process)
│   │
│   │   bellum-recon: fast model (kimi/k2.5), yolo, has Task tool
│   │   Reads findings/target.json → scans → writes findings/surfaces.json
│   │
│   │   LLM fires 4 Task calls in ONE message → parallel execution:
│   │
│   ├── Task("BLE scan 15s")                            ← DEPTH 1 (subagent)
│   │   └── Bash: python3 scripts/hardware/ble_scan.py --duration 15
│   │       → returns: '{"devices": [{"name":"QUADRUPED-XX","mac":"AA:BB:...","rssi":-42}]}'
│   │
│   ├── Task("nmap service scan 192.168.4.0/24")        ← DEPTH 1 (parallel)
│   │   └── Bash: nmap -sV -T4 192.168.4.0/24 -oJ /tmp/nmap.json && cat /tmp/nmap.json
│   │       → returns: '{"hosts": [{"ip":"192.168.4.1","ports":[22,8080,9090]}]}'
│   │
│   ├── Task("SubGHz scan 300-900MHz for 20s")          ← DEPTH 1 (parallel)
│   │   └── Bash: python3 scripts/hardware/subghz_scan.py --range 300-900 --dur 20
│   │       → returns: '{"signals": []}'
│   │
│   └── Task("WiFi scan nearby networks")               ← DEPTH 1 (parallel)
│       └── Bash: python3 scripts/hardware/wifi_scan.py
│           → returns: '{"networks": [{"ssid":"RobotAP-5G","bssid":"..."}]}'
│
│   bellum-recon merges 4 results → Write: findings/surfaces.json
│   <promise>RECON_COMPLETE</promise>
│   Ralph loop: gate passed? → yes (3 surfaces). Process exits.
│
│   [ORCHESTRATOR reads findings/surfaces.json, validates gate]
│
├─── opencode -p --agent bellum-research [prompt]       ← DEPTH 0 (fresh process)
│   │
│   │   bellum-research: strong model (claude-sonnet), yolo, has Task + WebSearch
│   │   Reads surfaces.json → researches → writes findings/intel.json
│   │
│   │   LLM fires 1 Task per surface → parallel research:
│   │
│   ├── Task("Research BLE:QUADRUPED-XX")               ← DEPTH 1
│   │   ├── WebSearch: "QUADRUPED robot BLE vulnerability 2025 2026"
│   │   ├── WebFetch: (CVE detail page)
│   │   ├── Bash: python3 scripts/recon/cve_search.py "QUADRUPED"
│   │   └── Bash: python3 scripts/recon/github_search.py "QUADRUPED BLE exploit"
│   │       → returns: "CVE-2025-XXXXX found. Existing Bleak PoC on GitHub. No BLE auth."
│   │
│   ├── Task("Research HTTP:192.168.4.1:8080")          ← DEPTH 1 (parallel)
│   │   ├── WebSearch: "QUADRUPED robot web API"
│   │   ├── Bash: python3 scripts/recon/shodan_search.py "QUADRUPED"
│   │   └── WebFetch: (API docs)
│   │       → returns: "REST API with /api/cmd endpoint. No authentication."
│   │
│   └── Task("Research SSH:192.168.4.1:22")             ← DEPTH 1 (parallel)
│       ├── WebSearch: "QUADRUPED default SSH credentials"
│       └── Bash: python3 scripts/recon/cve_search.py "OpenSSH 8.9"
│           → returns: "Default creds admin:admin common for this brand."
│
│   bellum-research merges → Write: findings/intel.json (3 hypotheses)
│   <promise>RESEARCH_COMPLETE</promise>
│
│   [ORCHESTRATOR reads findings/intel.json, validates gate]
│
├─── opencode -p --agent bellum-enumerate [prompt]      ← DEPTH 0 (fresh process)
│   │
│   │   bellum-enumerate: strong model, yolo, NO Task tool (sequential only)
│   │   Reads surfaces.json + intel.json → probes target → writes findings/vectors.json
│   │
│   │   SEQUENTIAL — avoid BLE connection conflicts from parallel access
│   │
│   ├── Hypothesis H1: BLE GATT write
│   │   ├── Bash: python3 scripts/hardware/ble_enumerate.py AA:BB:CC:DD:EE:FF
│   │   ├── Bash: python3 scripts/hardware/ble_read.py AA:BB:CC:DD:EE:FF 0xFFE1
│   │   └── → CONFIRMED: 0xFFE1 writable, no auth, little-endian, byte[0]=cmd byte[1-2]=params
│   │
│   ├── Hypothesis H3: REST API
│   │   ├── Bash: curl -s http://192.168.4.1:8080/api/
│   │   ├── Bash: curl -s -X POST http://192.168.4.1:8080/api/cmd -H 'Content-Type: application/json' -d '{"action":"status"}'
│   │   └── → CONFIRMED: /api/cmd accepts POST, JSON body, no auth
│   │
│   └── Write: findings/vectors.json  (V1: BLE write [CRITICAL], V2: REST API [CRITICAL])
│   <promise>ENUM_COMPLETE</promise>
│
│   [ORCHESTRATOR reads findings/vectors.json, validates gate, enters pivot loop]
│
├─── FOR vector IN vectors.vector_priority:             ← DETERMINISTIC (orchestrator TS)
│   │
│   └── opencode -p --agent bellum-exploit [prompt]     ← DEPTH 0 (fresh process)
│       │
│       │   bellum-exploit: strongest model (claude-sonnet), yolo (or HITL via plugin)
│       │   Reads vectors.json + intel.json → crafts + executes exploit
│       │
│       ├── WebSearch: "BLE GATT write Bleak movement command example python"
│       ├── Read: findings/intel.json (protocol details)
│       ├── Bash: python3 -c "payload = bytes([0x01, 0x02, 0x00, 0x32]); print(payload.hex())"
│       ├── Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 01020032
│       │         ↑ YOLO: -p mode auto-approves. Fires immediately.
│       │         ↑ (If BELLUM_HITL=true: permission.ask plugin intercepts, prompts user)
│       ├── → Robot moves forward!
│       ├── Bash: python3 scripts/hardware/ble_write.py AA:BB:CC:DD:EE:FF 0xFFE1 00000000
│       ├── → Robot stops!
│       └── Write: findings/exploit_V1.json { "success": true, "impact": "full movement control" }
│       <promise>EXPLOIT_COMPLETE</promise>
│
│   ORCHESTRATOR reads findings/exploit_V1.json:
│     success === true? → break out of for loop ✓
│     success === false? → continue to next vector (V2: REST API)
│     all vectors failed? → proceed to report anyway
│
└─── opencode -p --agent bellum-report [prompt]         ← DEPTH 0 (fresh process)
    │
    │   bellum-report: fast model (kimi/k2.5), yolo, read-only (no Bash, no hardware)
    │   Reads ALL findings/* → writes reports/bellum-{id}.md
    │
    ├── Glob: findings/*.json
    ├── Read: findings/target.json
    ├── Read: findings/surfaces.json
    ├── Read: findings/intel.json
    ├── Read: findings/vectors.json
    ├── Read: findings/exploit_V1.json
    └── Write: reports/bellum-1709913600.md

    <promise>REPORT_COMPLETE</promise>
```

### Why This Architecture Avoids All Upstream Bugs

| Bug | Why It Doesn't Affect Us |
|-----|--------------------------|
| **Permission inheritance** ([#12566](https://github.com/anomalyco/opencode/issues/12566)) | Each phase is `opencode -p` (auto-approves everything). Plus global `"*": "allow"` config as belt-and-suspenders. |
| **No nested task delegation** ([#7296](https://github.com/anomalyco/opencode/issues/7296)) | Phase agents are depth 0. Their Task subagents are depth 1. No depth 2 needed. |
| **Plan mode bypass** ([#6527](https://github.com/anomalyco/opencode/issues/6527)) | We don't use Plan mode. All agents are in build/execution mode. |
| **No async tasks** ([#15069](https://github.com/anomalyco/opencode/issues/15069)) | Parallel = multiple Task calls in one LLM message (works today). Phase-to-phase is sequential (fine for attack chain). |

### Fork Fix Checklist (Minimal)

Even though the architecture avoids most bugs, we still want these fork fixes for robustness:

```typescript
// packages/opencode/src/session/task.ts — our modifications

// FIX 1: Propagate parent permission config to child session (~5 lines)
const childSession = await createSession({
    agent: subagentName,
    parent: parentSession.id,
    permission: parentSession.agent.permission ?? globalConfig.permission,
});

// FIX 2: Make task delegation configurable per agent (~3 lines)
// In agent frontmatter: `task: true` or `task: false`
// Default: true for primary agents, false for subagents (unchanged from upstream)
// Our agents set `task: true` explicitly
```

Total fork diff: **~8 lines changed in `task.ts`**. Everything else is additive (new files in `src/bellum/`).

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

import { exec } from "child_process";
import { promisify } from "util";
import { readJson, writeJson, checkHardware, fileExists } from "./util";
import { validateSurfaces, validateIntel, validateVectors, validateExploit } from "./gates";

const run = promisify(exec);

interface BellumConfig {
    target: string;
    maxReconIter: number;     // default 10
    maxResearchIter: number;  // default 15
    maxEnumIter: number;      // default 10
    maxExploitIter: number;   // default 8
    maxReportIter: number;    // default 3
    hitl: boolean;            // default false (full yolo)
}

// Each phase = a separate `opencode -p` process invocation.
// -p mode auto-approves all permissions (yolo).
// The ralph loop is implemented by re-invoking until gate passes or max iterations hit.
async function runPhase(opts: {
    agent: string;
    prompt: string;
    gate: () => boolean;
    maxIter: number;
    env?: Record<string, string>;
}): Promise<boolean> {
    for (let i = 0; i < opts.maxIter; i++) {
        const envStr = Object.entries(opts.env ?? {})
            .map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ");

        // Each iteration is a fresh opencode -p invocation.
        // The agent reads its previous work from findings/*.json files.
        await run(
            `${envStr} opencode -p ${JSON.stringify(opts.prompt)} --agent ${opts.agent} -q`,
            { timeout: 300_000 } // 5 min timeout per iteration
        );

        if (opts.gate()) return true; // phase complete
        // else: re-iterate — agent will read its own output from disk next time
    }
    return false; // max iterations exhausted, gate never passed
}

export async function runEngagement(config: BellumConfig) {
    const engagementId = `bellum-${Date.now()}`;

    // PHASE 0: Target acquisition (no LLM — deterministic hardware check)
    const hardware = await checkHardware();
    await writeJson("findings/target.json", {
        engagement_id: engagementId,
        target: config.target,
        hardware,
        timestamp: new Date().toISOString(),
    });
    console.log(`[BELLUM] Engagement ${engagementId} started.`);
    console.log(`[BELLUM] Hardware: ${JSON.stringify(hardware)}`);

    // PHASE 1: Recon
    console.log("[BELLUM] Phase 1: Reconnaissance");
    const reconOk = await runPhase({
        agent: "bellum-recon",
        prompt: `Discover all wireless and network attack surfaces for: ${config.target}. ` +
                `Hardware available: ${JSON.stringify(hardware)}. ` +
                `Read findings/target.json. Write results to findings/surfaces.json. ` +
                `Output <promise>RECON_COMPLETE</promise> when done.`,
        gate: () => validateSurfaces("findings/surfaces.json"),
        maxIter: config.maxReconIter,
    });
    if (!reconOk) return await runReport(engagementId, "No attack surfaces discovered");

    // PHASE 2: Research
    console.log("[BELLUM] Phase 2: Research");
    const researchOk = await runPhase({
        agent: "bellum-research",
        prompt: `Research vulnerabilities for discovered surfaces. ` +
                `Read findings/surfaces.json. Write results to findings/intel.json. ` +
                `Output <promise>RESEARCH_COMPLETE</promise> when done.`,
        gate: () => validateIntel("findings/intel.json"),
        maxIter: config.maxResearchIter,
    });
    if (!researchOk) return await runReport(engagementId, "No attack hypotheses formed");

    // PHASE 3: Enumeration
    console.log("[BELLUM] Phase 3: Enumeration");
    const enumOk = await runPhase({
        agent: "bellum-enumerate",
        prompt: `Deep-dive attack hypotheses. Confirm or reject each. ` +
                `Read findings/surfaces.json + findings/intel.json. ` +
                `Write confirmed vectors to findings/vectors.json. ` +
                `Output <promise>ENUM_COMPLETE</promise> when done.`,
        gate: () => validateVectors("findings/vectors.json"),
        maxIter: config.maxEnumIter,
    });
    if (!enumOk) return await runReport(engagementId, "No exploitable vectors confirmed");

    // PHASE 4+5: Exploit + Pivot (deterministic for loop)
    const vectors = await readJson("findings/vectors.json");
    let exploitSuccess = false;

    for (const vectorId of vectors.vector_priority) {
        console.log(`[BELLUM] Phase 4: Exploit → vector ${vectorId}`);
        const ok = await runPhase({
            agent: "bellum-exploit",
            prompt: `Exploit vector ${vectorId}. ` +
                    `Read findings/vectors.json + findings/intel.json. ` +
                    `Craft and execute PoC. Write to findings/exploit_${vectorId}.json. ` +
                    `Output <promise>EXPLOIT_COMPLETE</promise> when done.`,
            gate: () => validateExploit(`findings/exploit_${vectorId}.json`),
            maxIter: config.maxExploitIter,
            env: config.hitl ? { BELLUM_HITL: "true" } : {},
        });
        if (ok) { exploitSuccess = true; break; }
        // else: PIVOT — for loop continues to next vector
        console.log(`[BELLUM] Vector ${vectorId} failed. Pivoting...`);
    }

    // PHASE 6: Report (always runs)
    return await runReport(
        engagementId,
        exploitSuccess ? "Exploitation successful" : "All vectors attempted"
    );
}

async function runReport(engagementId: string, summary: string) {
    console.log("[BELLUM] Phase 6: Report");
    await writeJson("findings/summary.json", { engagementId, summary });
    await runPhase({
        agent: "bellum-report",
        prompt: `Generate pentest report. Read ALL files in findings/. ` +
                `Write report to reports/bellum-${engagementId}.md. ` +
                `Output <promise>REPORT_COMPLETE</promise> when done.`,
        gate: () => fileExists(`reports/bellum-${engagementId}.md`),
        maxIter: 3,
    });
    console.log(`[BELLUM] DONE. Report: reports/bellum-${engagementId}.md`);
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

## Summary: What Makes v3.1 Different

| Aspect | v1 | v2 | v3 | v3.1 |
|--------|-----|-----|-----|------|
| **State management** | LLM (fragile) | Orchestrator + ralph loops | Same | Same |
| **HITL** | Everywhere | Exploit only | Yolo default | **Yolo via `-p` mode + `"*": "allow"` + plugin** |
| **Subagents** | Not specified | Mentioned | Full spawn tree | **Grounded in real upstream bugs + workarounds** |
| **Spawn model** | N/A | N/A | Nested subagents | **`opencode -p` per phase (depth 0) + Task (depth 1)** |
| **Permission model** | N/A | N/A | Assumed inheritance | **-p auto-approve + global allow + plugin fallback** |
| **Upstream bugs** | Not considered | Not considered | Not considered | **3 bugs documented, all sidestepped by architecture** |
| **Fork diff** | N/A | ~200 LOC | ~230 LOC | **~8 lines in task.ts + ~230 LOC additive** |
| **Parallelism** | None | Within-phase | Concrete | **Multiple Task calls in one message (proven pattern)** |
| **Orchestrator** | N/A | Pseudocode | Real TS | **Real TS using `opencode -p` process invocations** |
| **Demo readiness** | Theoretical | Plausible | Demoable | **Tested against real OpenCode constraints** |
