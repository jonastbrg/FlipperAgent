---
name: ralph-loop
description: "Start an autonomous pentest loop. Spawns fresh-context subagents for each phase. Use: /ralph-loop"
---

# Ralph Loop — Autonomous Pentest Orchestrator

When invoked, you become the **orchestrator**. You do NOT execute phases yourself. You spawn subagents with fresh context for each phase, monitor progress, and advance the state machine.

## How It Works

```
You (orchestrator, light context)
  ├── Spawn subagent: @recon   → reads nothing, scans everything, writes findings/recon.json
  ├── Spawn subagent: @research → reads recon.json, does OSINT, writes findings/research.json
  ├── Spawn subagent: @enumerate → reads recon+research, probes targets, writes findings/enumerate.json
  ├── Spawn subagent: @exploit  → reads all findings, asks user approval, writes findings/exploit.json
  └── Spawn subagent: @report   → reads all findings, writes report
```

Each subagent gets fresh context — only the disk state (findings/, engagement_state.json, progress.txt) carries between phases. This prevents context exhaustion on long engagements.

## Step-by-Step Protocol

### 1. Check State

Read `engagement_state.json` and `progress.txt`. Determine what phase to run next.

If neither exists, this is a new engagement. Initialize:
```json
{
  "engagement_id": "<random-hex-8>",
  "started_at": "<ISO-8601>",
  "phase": "recon",
  "targets_discovered": [],
  "vulnerabilities": [],
  "credentials_found": [],
  "attack_chains": [],
  "phases_completed": [],
  "notes": "",
  "todo_list": []
}
```

### 2. Spawn Phase Subagent

Use the **Agent tool** to spawn a subagent for the current phase. Each subagent:
- Gets the phase-specific agent prompt (`.opencode/agents/{phase}.md`)
- Has access to all MCP tools and skills
- Reads prior findings from `findings/`
- Writes its output to `findings/{phase}.json`
- Runs with fresh context (no prior conversation history)

```
Agent(
  prompt="You are running the {PHASE} phase of a pentest engagement.

  SCOPE: {scope from engagement_state.json or user-defined}

  Read prior findings from findings/ directory.
  Execute the phase using MCP tools.
  Write results to findings/{phase}.json.
  Update engagement_state.json with any new targets/vulns found.
  Append a summary to progress.txt.

  {content of .opencode/agents/{phase}.md}",

  model: "sonnet"  // or haiku for recon, opus for exploit
)
```

**Model routing per phase:**
- `recon` → sonnet (straightforward scanning)
- `research` → sonnet (OSINT, web search)
- `enumerate` → sonnet (active probing)
- `exploit` → opus (needs judgment for HIGH-risk actions) or current session (so user can approve)
- `report` → haiku (template-following)

### 3. Check Results

After the subagent returns, check if `findings/{phase}.json` was produced and has content (>10 bytes). If yes, advance to the next phase. If not, retry (max 3 attempts per phase).

### 4. Advance State

Update `engagement_state.json`:
- Add current phase to `phases_completed`
- Set `phase` to the next phase
- Increment iteration count

### 5. Repeat

Go back to step 2 with the next phase. Continue until all phases are complete or max iterations reached.

### 6. Exploit Phase — Special Handling

The exploit phase involves HIGH-risk actions. Two options:

**Option A (recommended):** Run the exploit phase in the CURRENT session (not as a subagent) so the user can approve each action interactively. Load `skill("campaign")` for the approval protocol.

**Option B:** Spawn the exploit subagent but with `HITL=true` behavior — the subagent explains each action and waits for approval before executing.

### 7. Parallel Subagents

For phases with multiple independent targets, spawn parallel subagents:

```
# If recon found 3 BLE devices + 2 WiFi networks:
Agent(prompt="Enumerate BLE device AA:BB:CC:DD:EE:FF ...", model="sonnet", run_in_background=true)
Agent(prompt="Enumerate BLE device 11:22:33:44:55:66 ...", model="sonnet", run_in_background=true)
Agent(prompt="Enumerate WiFi network MHM-Wifi ...", model="sonnet", run_in_background=true)
```

Merge their findings when all complete.

## Phase Transitions

```
recon → research       When: findings/recon.json exists with targets
research → enumerate   When: findings/research.json exists with prioritized vectors
enumerate → exploit    When: findings/enumerate.json exists with attack surface mapped
exploit → report       When: findings/exploit.json exists (or all vectors attempted)
```

## What You (Orchestrator) Do vs What Subagents Do

**You do:**
- Read state files
- Decide which phase to run
- Spawn subagents with the right prompt + model
- Check if findings were produced
- Advance the state machine
- Handle the exploit phase interactively (for user approval)
- Summarize progress to the user between phases

**Subagents do:**
- Read prior findings from disk
- CALL MCP tools (ble_scan, marauder_scan_ap, nmap, etc.)
- Write findings to disk
- Update engagement_state.json

**You do NOT:**
- Call MCP tools directly (except during exploit phase for user approval)
- Hold scan results in your context (they're on disk)
- Re-read findings that subagents already processed

## Resuming

If `engagement_state.json` already exists with completed phases, skip those and continue from the current phase. This makes ralph resumable across sessions.

## Approval Rules

Risk levels per tool are defined in `risk.py` and the primary agent. The rule: LOW=free, MEDIUM=log rationale, **HIGH=ask user first**, BLOCKED=refuse.
