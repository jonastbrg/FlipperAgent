---
name: wifi-attack
description: "WiFi reconnaissance and attack methodology via ESP32 Marauder — scanning, deauth, evil twin, captive portal, and KARMA attacks"
---

# WiFi Attack Methodology (ESP32 Marauder)

## Overview

The Flipper Zero's ESP32 Marauder module provides WiFi offensive capabilities. The ESP32 handles 802.11 frame injection and monitoring; the Flipper provides the control interface. All WiFi attacks require the Marauder firmware flashed to the ESP32 dev board attached to the Flipper's GPIO.

## Phase 1: Reconnaissance — WiFi Scanning

### AP Scanning
```
marauder_scan_ap(timeout=15)
```
Captures: SSID, BSSID, channel, RSSI, encryption type (Open/WEP/WPA/WPA2/WPA3), hidden status.

**Analysis priorities:**
- **Open networks** — immediate credential harvesting opportunity via evil twin
- **WPA2-Personal** — deauth + handshake capture viable
- **WPA3** — deauth still works for DoS but handshake capture requires Dragonblood-class vulns
- **WEP** — trivially breakable but rare in modern deployments
- **Hidden SSIDs** — revealed by client probe requests during deauth

### Client Scanning
```
marauder_scan_station(timeout=15)
```
Captures: client MAC, associated AP, probe requests (SSIDs the client is looking for), signal strength.

**Probe requests are gold:**
- Reveal networks the device has connected to previously
- Enable KARMA attacks (respond to probes with matching SSID)
- Fingerprint device type (Apple devices probe differently than Android)

### Channel Selection
- Most targets on channels 1, 6, 11 (non-overlapping 2.4 GHz)
- 5 GHz channels (36-165) require ESP32 support and are less commonly attacked
- Focus on the target AP's channel for deauth efficiency

## Phase 2: Deauth Attacks

### Purpose
Deauthentication forces clients to disconnect and reconnect, enabling:
1. **Handshake capture** — WPA2 4-way handshake during reconnect
2. **Client redirection** — force clients onto evil twin
3. **Denial of service** — keep target network unusable
4. **Hidden SSID reveal** — client reconnect exposes SSID in probe request

### Execution
```
marauder_deauth(target_bssid="AA:BB:CC:DD:EE:FF", channel=6, duration=30)
```

**Methodology:**
1. Scan APs to identify target network
2. Scan stations to identify connected clients
3. Select specific client MACs or broadcast deauth
4. Send deauth frames (reason code 7 = "Class 3 frame received from nonassociated STA")
5. Monitor for reconnection attempts
6. Capture handshake during reconnect

### Duration Guidelines
- **Handshake capture**: 10-30 seconds (just need one reconnect)
- **Client redirect to evil twin**: 60-120 seconds (sustained pressure)
- **DoS assessment**: document capability, do NOT sustain

### Legal Considerations
- Deauth attacks are **illegal** in most jurisdictions without explicit written authorization
- FCC Part 15 prohibits intentional interference with authorized radio communications
- CFAA and equivalents in EU (Computer Misuse Act), AU, etc. apply
- **ALWAYS** verify scope of engagement authorization covers WiFi testing
- **ALWAYS** limit to target networks only — collateral deauth is scope violation
- Document authorization reference in findings

## Phase 3: Evil Twin / Rogue AP

### Concept
Create a fake AP that mimics the target network. Clients connect to the stronger signal and route traffic through the attacker.

### Setup
```
marauder_evil_twin(ssid="CorpWiFi", channel=6, captive_portal=true)
```

**Steps:**
1. Clone target AP's SSID exactly (case-sensitive)
2. Match channel and encryption (or use Open for captive portal)
3. Start deauth on real AP to force client migration
4. Serve captive portal on the evil twin
5. Capture credentials submitted to portal

### Portal Templates
Effective captive portal pages mimic:
- **Corporate SSO login** — "Your session has expired, please re-authenticate"
- **Hotel/airport WiFi** — "Accept terms and enter room number / booking reference"
- **ISP maintenance** — "Firmware update requires password verification"
- **OAuth consent** — fake Google/Microsoft sign-in

### Detection Evasion
- Match target AP's BSSID if possible (MAC spoofing)
- Use same channel as target
- Ensure evil twin signal is stronger than real AP (proximity)
- Serve HTTPS with a self-signed cert (triggers browser warning but looks more legitimate)

## Phase 4: Captive Portal Credential Harvesting

### How It Works
1. Client connects to evil twin (open network)
2. OS detects captive portal (HTTP probe to connectivity check URL returns non-200)
3. Captive portal browser opens automatically
4. User sees login page, enters credentials
5. Credentials logged, user redirected to real internet (optional)

### Credential Capture
Credentials are captured in the Marauder log. After engagement:
```
marauder_get_credentials()
```

**Post-capture actions:**
- Hash passwords immediately — never store plaintext longer than necessary
- Test credentials against target services (with authorization)
- Check for credential reuse across services
- Document in findings with severity HIGH

### OS-Specific Captive Portal Behavior
| OS | Detection URL | Portal Browser |
|----|--------------|----------------|
| iOS/macOS | captive.apple.com/hotspot-detect.html | CaptiveNetworkSupport (limited browser) |
| Android | connectivitycheck.gstatic.com/generate_204 | Chrome Custom Tab |
| Windows | www.msftconnecttest.com/connecttest.txt | Default browser |

## Phase 5: KARMA Attacks

### Concept
KARMA exploits automatic WiFi reconnection. Devices constantly probe for known networks. A KARMA AP responds to ALL probe requests, claiming to be whatever network the device is looking for.

### Execution
```
marauder_karma(enable=true)
```

**How it works:**
1. Client device probes: "Is 'HomeWiFi' here?"
2. KARMA AP responds: "Yes, I am 'HomeWiFi'"
3. Client connects automatically (if no certificate pinning / WPA3-SAE)
4. Traffic flows through attacker

**Effective against:**
- Devices probing for open networks (hotels, airports, coffee shops)
- Older devices without probe request randomization
- IoT devices with hardcoded WiFi credentials

**Less effective against:**
- Modern iOS/Android with MAC randomization and probe suppression
- WPA2/WPA3 networks (client expects authentication)
- Enterprise WPA2 with certificate validation

## Phase 6: Post-Capture Analysis

### Credential Analysis
1. **Categorize**: email/password, SSO tokens, session cookies, API keys
2. **Validate**: test against authorized target services only
3. **Credential reuse**: check if same password works on other in-scope services
4. **Privilege level**: determine what access the credentials grant

### Network Pivot
If authorized for lateral movement:
1. Use captured credentials to authenticate to real network
2. Scan internal network for services
3. Attempt default credentials on discovered services
4. Document network topology discovered

### Traffic Analysis
If performing MITM via evil twin:
1. Capture DNS queries — reveals internal service names
2. HTTP traffic — credentials, API calls, sensitive data
3. TLS connections — note which services use certificate pinning (immune to MITM)
4. Document all cleartext credential observations

## Operational Security

- **Beacon spam** (`marauder_beacon_spam`) floods the area with fake SSIDs — useful for confusion but highly visible. Use sparingly.
- **Probe flood** (`marauder_probe_flood`) generates fake probe requests — can overwhelm monitoring systems.
- Monitor for wireless IDS/IPS (Cisco CleanAir, Aruba RFProtect, etc.) — they detect deauth floods and rogue APs.
- Keep attack duration minimal — longer attacks increase detection probability.
- Use directional antennas when possible to limit blast radius.

## Findings Documentation

For each WiFi finding, document:
- Attack type (deauth, evil twin, KARMA)
- Target network SSID and BSSID
- Number of clients affected
- Credentials captured (redacted in report, full in secure appendix)
- Duration of attack
- Whether detection systems flagged the activity
- Remediation: WPA3-SAE, 802.1X with certs, WIDS deployment, client probe suppression
