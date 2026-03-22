---
name: ralph-loop
description: "Start an autonomous pentest loop. Spawns fresh-context subagents for each phase. Use: /ralph-loop"
---

# Ralph Loop — Autonomous Pentest Orchestrator

When invoked, you become the **orchestrator**. You do NOT execute phases yourself. You spawn subagents with fresh context for each phase, monitor progress, and advance the state machine.

## How It Works

```
You (orchestrator, light context)
  ├── Spawn Agent: recon   → scans everything, writes findings/recon.json
  ├── Spawn Agent: research → OSINT on targets, writes findings/research.json
  ├── Spawn Agent: enumerate → probes targets, writes findings/enumerate.json
  ├── You directly: exploit  → ask user approval for each HIGH-risk action
  └── Spawn Agent: report   → compiles findings into report
```

Each subagent gets fresh context. Only disk state carries between phases.

## Protocol

### 1. Read State

Read `engagement_state.json` and `progress.txt`. If neither exists, initialize a new engagement.

### 2. Spawn Phase Subagent

Use the **Agent tool** for each phase:

```
Agent(
  description: "Run {phase} phase",
  prompt: "You are running the {PHASE} phase of a pentest.
    SCOPE: {scope}
    Read findings/ for prior results.
    CALL MCP tools to execute this phase.
    Write results to findings/{phase}.json.
    {paste content of .opencode/agents/{phase}.md}",
  model: "sonnet"
)
```

**Model per phase:** recon→sonnet, research→sonnet, enumerate→sonnet, exploit→current session (user approval), report→haiku.

### 3. Check & Advance

After each subagent returns:
- Check `findings/{phase}.json` exists and has content
- If yes → advance phase in `engagement_state.json`
- If no → retry (max 3), then force-advance

### 4. Exploit Phase — Run Directly

Do NOT spawn a subagent for exploit. Run it yourself so the user can approve each HIGH-risk action. Load `skill("campaign")` for the approval protocol.

### 5. Parallel Targets

When multiple independent targets exist, spawn parallel subagents:
```
Agent(prompt="Enumerate BLE device X...", model="sonnet", run_in_background=true)
Agent(prompt="Enumerate WiFi network Y...", model="sonnet", run_in_background=true)
```

### 6. Resume

If engagement_state.json has completed phases, skip them and continue.

## You vs Subagents

**You:** read state, spawn agents, check results, advance phases, handle exploit interactively, summarize to user.

**Subagents:** read findings from disk, CALL tools, write findings to disk. Fresh context each time.
