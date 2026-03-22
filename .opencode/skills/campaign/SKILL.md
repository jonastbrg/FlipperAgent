---
name: campaign
description: "Run a sustained security assessment campaign — a real pentest, not a simulation"
---

# Campaign — What It Is

A campaign is a **real penetration test**. Not a simulation. Not a description of what you would do. You have real tools connected to real hardware. You CALL those tools, collect real results, and make real findings.

A campaign progresses through five phases. Each phase uses specific tools to produce specific evidence. You cannot skip phases. You cannot fabricate results. If you didn't call a tool, you don't have data.

## The Iron Rules

1. **CALL tools, don't describe them.** You have MCP tools available as function calls. When this document says "scan for BLE devices," that means CALL `ble_scan(duration=15)`. Do NOT write "I would run ble_scan and expect to find..." — that is fabrication.

2. **LOAD skills before using them.** You have 15+ skills available. To use one, CALL the skill tool: `skill("ble-exploitation")`. Do NOT reference skill content from memory — load it.

3. **Results come from tools, not from you.** If `ble_scan` returns 3 devices, you have 3 devices. If it returns 0, you have 0. Do NOT add devices you "expect" to see. Do NOT embellish tool output.

4. **WRITE findings to disk.** Your text output is ephemeral — it dies when the session ends. Findings must be written to `findings/{phase}.json` using file write tools. If it's not on disk, it doesn't exist.

5. **ASK before dangerous actions.** Any tool that TRANSMITS (subghz_tx, ir_tx), WRITES to hardware (ble_write_char, rfid_write, nfc_emulate), INJECTS (badusb_execute), or ATTACKS (marauder_deauth) requires explicit user approval BEFORE you call it. Explain what you will do, what the expected effect is, and what could go wrong. Then wait for approval.

6. **STAY in scope.** Only target what the operator authorized. If you discover something outside scope, report it but do NOT probe it without asking.

## The Five Phases

Every campaign follows this progression. The target protocol doesn't matter — BLE, WiFi, SubGHz, NFC, RFID, network, or a mix. The methodology is always the same.

### Phase 1: RECON (Passive Discovery)

**Goal:** Find everything in range. Cast a wide net across all RF modalities.

**What you do:**
- CALL `ble_scan` — discover BLE devices (name, address, RSSI, services)
- CALL `subghz_rx` at common frequencies (433920000, 315000000, 868000000) — capture RF signals
- CALL `nfc_detect` — check for NFC tags in proximity
- CALL `rfid_read` — check for 125kHz RFID tags
- CALL `marauder_scan_wifi` — enumerate WiFi networks (if ESP32 available)
- CALL `nmap_host_discovery` — find hosts on local network (if in scope)
- CALL `shodan_myip` — check external exposure

**Risk level:** LOW. All passive or minimally active. No approval needed.

**You are done when:** You've scanned every modality available to you and recorded what's there (including "nothing found" — absence is data).

**Output:** Write structured JSON to `findings/recon.json` with everything discovered, organized by modality.

### Phase 2: RESEARCH (Intelligence Gathering)

**Goal:** For each target found in recon, gather OSINT and known vulnerabilities.

**What you do:**
- Web search for manufacturer + model + CVE
- CALL `shodan_search` or `shodan_host` for internet-facing targets
- Look up FCC IDs, Bluetooth SIG entries, protocol documentation
- Check for prior art (GitHub repos, security advisories, conference talks)
- LOAD the relevant skill if one exists (e.g., `skill("protocol-analysis")`)

**Risk level:** LOW. No interaction with targets.

**You are done when:** Each target has a research profile: known vulns, protocol documentation, attack surface assessment, and a prioritized list of what to enumerate.

**Output:** Write to `findings/research.json` with per-target research profiles and a priority ranking of targets to enumerate.

### Phase 3: ENUMERATE (Active Probing)

**Goal:** Deep-probe each target to map every service, characteristic, entry point, and potential vulnerability.

**What you do:**
- CALL `ble_enumerate` — map all GATT services and characteristics per BLE device
- CALL `ble_read_char` — read every readable characteristic
- CALL `ble_subscribe` — monitor notification characteristics
- CALL `nmap_service_scan` / `nmap_vuln_scan` — fingerprint network services
- CALL `subghz_rx` + `subghz_decode_raw` — analyze captured signals (fixed code? rolling code?)
- CALL `nfc_detect` — deep-read tag data (type, UID, NDEF, sector structure)
- CALL `rfid_read` — full data dump of RFID tags

**Risk level:** MEDIUM. You are connecting to targets and actively probing. Log your rationale for each connection.

**You are done when:** Every target has a complete profile: services, characteristics (with properties like read/write/notify), open ports, signal analysis, identified vulnerabilities, and a list of attack vectors to try.

**Output:** Write to `findings/enumerate.json` with per-target enumeration data, identified vulnerabilities, and an attack graph (entry points → lateral movement → high-value targets).

### Phase 4: EXPLOIT (Controlled Attacks)

**Goal:** Demonstrate real impact by executing proof-of-concept exploits against confirmed vulnerabilities.

**What you do — WITH USER APPROVAL FOR EACH ACTION:**
- CALL `ble_write_char` — write to characteristics lacking authentication (⚠️ ASK FIRST)
- CALL `subghz_tx` / `subghz_tx_from_file` — replay captured signals (⚠️ ASK FIRST)
- CALL `nfc_emulate` — emulate cloned NFC credentials (⚠️ ASK FIRST)
- CALL `rfid_emulate` / `rfid_write` — clone/write RFID tags (⚠️ ASK FIRST)
- CALL `marauder_deauth` — WiFi deauth test (⚠️ ASK FIRST)
- CALL `badusb_execute` — HID injection (⚠️ ASK FIRST — highest impact)
- LOAD skills as needed: `skill("ble-exploitation")`, `skill("credential-attack")`, `skill("wifi-attack")`

**Risk level:** HIGH. Every action in this phase can cause physical-world effects. You MUST:
1. Explain exactly what you're about to do
2. State the expected effect ("this will send an unlock command to the BLE lock")
3. State what could go wrong ("if the device interprets this differently, it could factory reset")
4. Wait for explicit user approval
5. Document pre-state and post-state

**You are done when:** All feasible attack vectors have been attempted (or deliberately skipped with documented rationale). Each exploit attempt is recorded with success/failure, evidence, and impact.

**Output:** Write to `findings/exploit.json` with per-exploit records: target, vulnerability, technique, tools used, pre/post state, success boolean, evidence, impact, remediation.

### Phase 5: REPORT (Documentation)

**Goal:** Produce a professional pentest report.

**What you do:**
- Read all `findings/*.json` files
- Read `engagement_state.json` / `campaign_state.json` for the full engagement history
- Read `progress.txt` for operational notes
- LOAD `skill("pentest-report")` for report structure
- Write the report with: executive summary, methodology, findings table (severity + confidence), evidence, attack chains, and remediation recommendations

**Risk level:** LOW. No target interaction.

**Confidence levels for findings:**
- **Confirmed** — you called a tool and directly observed the vulnerability (e.g., ble_write_char succeeded without auth)
- **Likely** — strong evidence from enumeration but not exploited (e.g., writable characteristic found but write not attempted)
- **Possible** — theoretical based on research (e.g., firmware version has known CVE but not tested)

**Output:** Write the report to `findings/report.md` or `campaigns/{id}/FINAL_REPORT.md`.

## Campaign State

State persists across sessions in `engagement_state.json` or `campaigns/{id}/campaign_state.json` (for multi-target campaigns).

The state tracks:
- Current phase and completed phases
- Discovered targets with priority, status, and attack vectors
- Findings with severity and confidence
- Credentials found
- Attack chains linking multiple findings
- Decisions and approval records
- Todo list for next iteration

## Target Expansion

When attacking one target reveals new ones, the campaign grows:
- BLE device leaks WiFi credentials → add WiFi network as target
- WiFi network joined → nmap reveals new hosts → add as targets
- NFC badge cloned → access control system is now a target
- Firmware reveals API keys → cloud service is now a target

New targets inherit scope from their parent unless the operator explicitly excludes them. Always ask before expanding scope to a new protocol or network segment.

## The Ralph Loop

For autonomous operation, load `skill("ralph-loop")`. You become the orchestrator:

1. Spawn a fresh-context subagent for the current phase
2. Subagent reads findings from disk, calls tools, writes results
3. Check if findings were produced → advance to next phase
4. Exploit phase runs in your session (for user approval of HIGH-risk actions)
5. Repeat until all phases complete

State lives on disk (`findings/`, `engagement_state.json`), not in conversation context.

## Approval Summary

| Action Type | Risk | Approval Required |
|-------------|------|-------------------|
| Scan/detect (ble_scan, nfc_detect, rfid_read, subghz_rx, ir_rx) | LOW | No — execute freely |
| Research (web search, Shodan, OSINT) | LOW | No |
| Connect + read (ble_enumerate, ble_read_char, ble_subscribe) | MEDIUM | No — but log rationale |
| Network scan (nmap_service_scan, nmap_vuln_scan) | MEDIUM | No — but log rationale |
| RF transmit (subghz_tx, ir_tx) | HIGH | YES — ask user first |
| Hardware write (ble_write_char, rfid_write) | HIGH | YES — ask user first |
| Emulation (nfc_emulate, rfid_emulate) | HIGH | YES — ask user first |
| WiFi attack (marauder_deauth, beacon_spam, probe_flood) | HIGH | YES — ask user first |
| HID injection (badusb_execute) | HIGH | YES — ask user first |
| Scope expansion (probing new targets not in original scope) | HIGH | YES — ask user first |
| Internal paths, key files, secrets | BLOCKED | REFUSE — never do this |
