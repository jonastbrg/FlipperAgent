---
name: self-improve
description: "Continuously improve FlipperAgent's skills, docs, and agent definitions based on successes, failures, and learnings from campaigns and tool usage"
---

# Self-Improvement — Continuous Learning Loop

FlipperAgent learns from every engagement. The core principle:

**Use the model less. Convert reasoning into deterministic scripts.**

When you find yourself repeating a multi-step pattern (scan → enumerate → probe → report), don't keep reasoning through it every time. Write a script that does it in one call. The model decides WHAT to run. Code handles HOW.

```
BAD (20 model calls, 2000 tokens):
  Model: "I should scan BLE" → writes Python inline → reads output
  Model: "I should enumerate" → writes Python inline → reads output
  Model: "I should probe auth" → writes Python inline → reads output
  ... repeat for every step

GOOD (2 model calls, 200 tokens):
  Model: "Run full recon"
  Bash: python3 scripts/campaign_auto.py recon --duration 10
  Model: "Found writable char, probe it"
  Bash: python3 scripts/campaign_auto.py probe-auth ADDRESS UUID
```

This reduces token usage by 80-90%, removes approval friction, and improves accuracy (code doesn't hallucinate parameters).

## Available Automation Scripts

```bash
python3 scripts/campaign_auto.py recon --duration 10        # Full BLE + Flipper recon
python3 scripts/campaign_auto.py enumerate ADDRESS          # Complete GATT enumeration
python3 scripts/campaign_auto.py probe-auth ADDRESS UUID    # Test write auth
python3 scripts/campaign_auto.py device-info                # Flipper status + SD card
python3 scripts/campaign_auto.py full-scan --duration 10    # Scan + enumerate all devices
```

All output is JSON. Add new scripts when you discover repeating patterns.

FlipperAgent learns from every engagement. After tool calls, campaigns, and attack attempts, update the project's knowledge base so future sessions benefit.

## When to Self-Improve

Trigger this skill when:
- A tool call fails in an unexpected way (new error pattern)
- A CLI command has different syntax than documented (firmware quirk)
- A new attack technique works that isn't in the skills
- A campaign discovers a device category not covered by existing methodology
- You find a better way to chain tools together
- A risk classification turns out to be wrong (too high or too low)

## What to Update

### 1. Tool Reference (`.opencode/agents/tool-reference.md`)

Add new CLI commands, fix incorrect syntax, document firmware-specific quirks:

```markdown
## New: discovered that `lfrfid` not `rfid` is the correct command on FW 1.4.3
```

### 2. Context Knowledge (`.opencode/agents/context.md`)

Add discovered patterns, architecture insights, known issues:

```markdown
## Known Issues
- subghz rx blocks indefinitely — added: 2026-03-22
- rfid command is lfrfid on FW 1.4.3 — added: 2026-03-22
```

### 3. Skills (`.opencode/skills/*/SKILL.md`)

Update methodology based on real-world results:

```markdown
## Learned: WHOOP 5.0 requires encryption for fd4b0002 writes
## Previous assumption: WHOOP 4.0 protocol would transfer to 5.0
## Reality: Different service UUID (fd4b vs 6108), encryption enforced
## Update: always probe write auth before assuming unauthenticated access
```

### 4. Primary Agent (`.opencode/agents/flipper-agent.md`)

Add new heuristics, tool selection rules, or methodology updates:

```markdown
## Learned: BLE devices with Ambiq Apollo4 chip use ARM Cordio stack (6 CVEs)
## Action: always check chip manufacturer when enumerating BLE devices
```

### 5. Campaign Learnings (`campaigns/{id}/progress.txt`)

Per-campaign learnings that inform future campaigns:

```
[2026-03-22T10:30:00Z] WHOOP 5.0: fd4b0002 requires encryption. 4.0→5.0 protocol NOT transferable.
[2026-03-22T11:00:00Z] Ambiq Apollo4 Blue Plus uses Cordio BLE stack. Check CVE-2024-48984.
[2026-03-22T11:30:00Z] Static BLE address on WHOOP = trackable. Check RPA rotation on all targets.
```

## Self-Improvement Protocol

After each campaign iteration or significant tool interaction:

1. **Assess**: What worked? What failed? What was unexpected?
2. **Classify**: Is this a tool issue, methodology gap, or new knowledge?
3. **Locate**: Which file should be updated? (tool-reference, context, skill, agent)
4. **Update**: Make a targeted, minimal edit to the right file
5. **Verify**: Read the file back to confirm the update is correct
6. **Commit**: Include "self-improve:" prefix in commit message for tracking

## Update Rules

- **Add, don't delete**: Preserve existing knowledge. Add new entries, don't remove old ones.
- **Date your learnings**: Include timestamp so stale info can be identified.
- **Be specific**: "WHOOP 5.0 FW 50.36.1.0 requires encryption on fd4b0002" not "some devices need auth."
- **Link to evidence**: Reference campaign IDs, tool outputs, or error messages.
- **Don't over-generalize**: One device's behavior doesn't apply to all devices of that type.
- **Skills over agent**: Prefer updating skills (loaded on-demand) over the primary agent (always loaded). Keeps context window lean.

## Example: Post-Campaign Self-Improvement

After the WHOOP 5.0 campaign converged:

```
Files updated:
1. tool-reference.md: added "lfrfid" note, subghz rx timeout note
2. context.md: added "Known Issues" section with FW 1.4.3 quirks
3. ble-exploitation/SKILL.md: added "always probe write auth" rule
4. signal-analysis/SKILL.md: added Ambiq Cordio CVE reference
5. campaign/SKILL.md: added "check chip manufacturer" to enumeration phase
```

## Tracking Improvements

Commit self-improvement changes with this format:
```
self-improve: [what was learned] (from [campaign/tool/session])
```

Examples:
```
self-improve: add lfrfid command for RFID (from FW 1.4.3 testing)
self-improve: WHOOP 5.0 requires encryption on writes (from campaign 2efb0f4b)
self-improve: update BLE skill with auth probe methodology (from WHOOP assessment)
```
