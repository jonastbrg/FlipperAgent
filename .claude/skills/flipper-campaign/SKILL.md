---
name: flipper-campaign
description: "Run sustained security assessment campaigns against targets using the Ralph Wiggum autonomous loop pattern. Use when asked to start, continue, or manage a pentest campaign."
---

# Campaign Management

Campaigns are persistent, multi-session security assessments. State lives in `campaigns/<campaign_id>/campaign_state.json`. The campaign library is at `flipperzero-mcp/src/flipper_mcp/core/campaign.py`.

## Campaign Lifecycle

```
new campaign -> recon -> research -> enumerate -> exploit -> report
                 ^                                   |
                 +------------ iterate --------------+
```

Each campaign tracks: targets (expansion tree), attack vectors per target, findings, agent coordination, and review queues for HIGH-risk actions.

## Managing Campaigns via Python

All campaign management runs through the `CampaignManager` class. Execute from project root:

```bash
python3 -c "
import sys; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager, Target, AttackVector
mgr = CampaignManager('campaigns')

# List existing campaigns
import json
print(json.dumps(mgr.list_campaigns(), indent=2))
"
```

### Create a new campaign
```bash
python3 -c "
import sys, json; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager
mgr = CampaignManager('campaigns')
state = mgr.new_campaign(
    name='Office BLE Assessment',
    description='BLE device security audit',
    scope='All BLE devices within 30m of office desk'
)
print(json.dumps({'campaign_id': state.campaign_id, 'name': state.name}, indent=2))
"
```

### Load and inspect campaign state
```bash
python3 -c "
import sys, json; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager
mgr = CampaignManager('campaigns')
state = mgr.load('<CAMPAIGN_ID>')
print(json.dumps({
    'name': state.name, 'phase': state.current_phase,
    'iteration': state.iteration, 'targets': len(state.targets),
    'findings': state.total_findings, 'status': state.status,
}, indent=2))
"
```

### Add a target from scan results
```bash
python3 -c "
import sys, json; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager, Target
mgr = CampaignManager('campaigns')
mgr.load('<CAMPAIGN_ID>')
mgr.add_target(Target(
    name='Smart Lock',
    type='ble_device',
    address='AA:BB:CC:DD:EE:FF',
    discovered_via='ble_scan',
    metadata={'rssi': -45, 'vendor': 'Unknown'},
    priority=20
))
mgr.save()
print('Target added')
"
```

### Add a finding
```bash
python3 -c "
import sys, json; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager
mgr = CampaignManager('campaigns')
mgr.load('<CAMPAIGN_ID>')
mgr.add_finding('<TARGET_ID>', {
    'title': 'Writable characteristic accepts unauthenticated writes',
    'severity': 'high',
    'description': 'Characteristic 0x2A06 writable without pairing',
    'evidence': 'ble_write_char returned success with response=True',
    'vector_id': '<VECTOR_ID>'
})
print('Finding added')
"
```

## Ralph Wiggum Loop Pattern

The Ralph loop is the autonomous iteration engine. Each iteration:

1. **Read state** -- load `campaign_state.json`, determine current phase and next target
2. **Do work** -- execute the phase-appropriate actions using flipper-hardware skill
3. **Write findings** -- persist discoveries back to campaign state
4. **Advance** -- increment iteration, check convergence, transition phases

### Phase-Specific Work

| Phase | Actions | Tools Used |
|-------|---------|------------|
| **recon** | BLE scan, SubGHz RX, NFC detect, WiFi scan | `ble_scan.py`, `flipper_connect.py cli subghz rx ...` |
| **research** | OSINT on discovered devices, firmware lookup, CVE search | Web research, manufacturer docs |
| **enumerate** | GATT enumeration, service probing, protocol analysis | `ble_enumerate.py`, `ble_read_char` |
| **exploit** | Write to characteristics, replay signals, test auth bypass | `ble_write_char` (HIGH risk -- ask user), `subghz_tx` |
| **report** | Compile findings, generate summary, risk ratings | Read campaign state, format report |

### Phase Transitions

Advance phase when:
- **recon -> research**: No new devices found in 2+ consecutive scans
- **research -> enumerate**: All high-priority targets have research notes
- **enumerate -> exploit**: GATT enumeration complete for all reachable targets
- **exploit -> report**: All planned attack vectors attempted or abandoned
- **report -> recon**: Report delivered, but new scope or targets added

### Running the Loop

For a single iteration (recommended for interactive use):
```bash
# Read current state
python3 -c "
import sys, json; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager
mgr = CampaignManager('campaigns')
state = mgr.load('<CAMPAIGN_ID>')
target = mgr.get_next_target()
print(json.dumps({
    'phase': state.current_phase,
    'iteration': state.iteration,
    'next_target': {'id': target.id, 'name': target.name, 'status': target.status} if target else None
}, indent=2))
"

# ... execute phase work using flipper-hardware skill ...

# Advance iteration
python3 -c "
import sys; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager
mgr = CampaignManager('campaigns')
mgr.load('<CAMPAIGN_ID>')
can_continue = mgr.advance_iteration()
print(f'Iteration advanced. Can continue: {can_continue}')
"
```

For the full automated loop, use `/ralph-loop`. The agent spawns fresh-context subagents per phase, with exploit running in your session for approval.

## Target Expansion Tree

Campaigns support target discovery chains: scanning one target may reveal others.

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'flipperzero-mcp/src')
from flipper_mcp.core.campaign import CampaignManager, Target
mgr = CampaignManager('campaigns')
mgr.load('<CAMPAIGN_ID>')

# Add a child target discovered from a parent
mgr.add_child_target('<PARENT_TARGET_ID>', Target(
    name='Hub Device',
    type='ble_device',
    address='11:22:33:44:55:66',
    discovered_via='ble_enumerate of parent',
))

# View the tree
tree = mgr.get_expansion_tree()
print(json.dumps(tree, indent=2))
"
```

## Safety Integration

Campaign operations follow the flipper-hardware risk gates:

- **Recon/Research/Enumerate phases**: Mostly LOW/MEDIUM risk, proceed with logging
- **Exploit phase**: Contains HIGH-risk actions. Before any HIGH-risk tool call:
  1. Queue the action: `mgr.queue_for_review({...})`
  2. Log the decision: `mgr.log_decision(decision, rationale, reviewed_by)`
  3. Ask the user for confirmation
  4. Only then execute

When `HITL=true` is set in the environment, all exploit-phase actions require human confirmation regardless of risk level.

## Campaign State Schema

Key fields in `campaign_state.json`:
- `campaign_id`, `name`, `status` (active/paused/completed/aborted)
- `current_phase` (recon/research/enumerate/exploit/report)
- `iteration`, `max_iterations` (convergence guard)
- `targets[]` -- each with `attack_vectors[]`, `status`, `priority`
- `review_queue[]` -- HIGH-risk actions pending approval
- `decisions[]` -- audit trail of rationale for actions taken
- `total_findings`, `critical_findings`, `high_findings`, etc.
