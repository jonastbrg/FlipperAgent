---
name: credential-attack
description: "Credential testing methodology — default credential checking, password spraying, credential reuse, and OSINT for leaked credentials"
---

# Credential Attack Methodology

## Why Default Credentials Matter

Per ARTEMIS and OWASP research, default credentials are consistently the #1 exploit vector in IoT and embedded device penetration testing. Over 60% of IoT devices ship with default credentials that are never changed. This is the first thing to test — before any complex exploitation.

## Phase 1: Default Credential Checking

### Methodology
```
flipper_cred_check_default(target="192.168.1.1", service="http")
```

1. **Identify the device** — manufacturer, model, firmware version
2. **Look up known defaults** — from database below and online sources
3. **Test systematically** — try all known defaults for that device/service
4. **Document results** — success/failure, which credential worked

### Default Credentials by Service Type

**Network Equipment (Routers, Switches, Firewalls)**
| Manufacturer | Username | Password |
|-------------|----------|----------|
| Cisco | admin | admin |
| Cisco | cisco | cisco |
| Cisco (enable) | — | cisco |
| Netgear | admin | password |
| Netgear | admin | 1234 |
| TP-Link | admin | admin |
| D-Link | admin | (blank) |
| D-Link | admin | admin |
| Linksys | admin | admin |
| Ubiquiti | ubnt | ubnt |
| MikroTik | admin | (blank) |
| Fortinet | admin | (blank) |
| Fortinet | admin | fortinet |
| Palo Alto | admin | admin |
| SonicWall | admin | password |

**IP Cameras / DVRs / NVRs**
| Manufacturer | Username | Password |
|-------------|----------|----------|
| Hikvision | admin | 12345 |
| Hikvision | admin | admin12345 |
| Dahua | admin | admin |
| Dahua | 888888 | 888888 |
| Axis | root | pass |
| Axis | root | (blank) |
| Samsung (Hanwha) | admin | 4321 |
| Amcrest | admin | admin |
| Reolink | admin | (blank) |
| Foscam | admin | (blank) |
| Vivotek | root | (blank) |

**IoT / Smart Home**
| Device Type | Username | Password |
|------------|----------|----------|
| Smart plugs (Tuya) | admin | admin |
| Smart bulbs (generic) | admin | admin |
| Zigbee hubs | — | (no auth on local API) |
| MQTT brokers | (blank) | (blank) |
| Home Assistant | — | (setup wizard) |
| OpenHAB | admin | admin |

**Industrial / SCADA / ICS**
| System | Username | Password |
|--------|----------|----------|
| Siemens S7 | admin | admin |
| Allen-Bradley | admin | 1234 |
| Schneider | USER | USER |
| Modbus TCP | — | (no auth by design) |
| BACnet | — | (no auth by design) |
| OPC UA (default) | admin | admin |

**Databases**
| Database | Username | Password |
|----------|----------|----------|
| MySQL | root | (blank) |
| MySQL | root | root |
| PostgreSQL | postgres | postgres |
| MongoDB | — | (no auth default) |
| Redis | — | (no auth default) |
| Elasticsearch | — | (no auth pre-8.0) |
| CouchDB | admin | admin |

**Web Applications / Management Interfaces**
| Application | Username | Password |
|-------------|----------|----------|
| Tomcat | tomcat | tomcat |
| Tomcat | admin | admin |
| Jenkins | admin | admin |
| Grafana | admin | admin |
| phpMyAdmin | root | (blank) |
| WordPress | admin | admin |
| Joomla | admin | admin |
| Webmin | root | (system root pw) |
| IPMI/BMC | ADMIN | ADMIN |
| iLO | Administrator | (serial number) |
| iDRAC | root | calvin |

**Embedded / Telnet / Serial**
| Device | Username | Password |
|--------|----------|----------|
| BusyBox (generic) | root | (blank) |
| BusyBox (generic) | admin | admin |
| OpenWRT | root | (blank) |
| Raspberry Pi | pi | raspberry |
| Arduino (Yun) | root | arduino |

### Testing Order
1. Try the most common credential for that exact device
2. Try admin:(blank), admin:admin, admin:password, root:root
3. Try manufacturer-specific defaults from table above
4. Try the device model number or serial number as password
5. Try common patterns: company name, device name, 12345, 123456

## Phase 2: Password Spraying

### When to Use
- Default credentials failed
- Multiple accounts discovered (user enumeration succeeded)
- Login form or API endpoint identified

### Methodology
```
flipper_cred_spray(
  target="https://target.local/login",
  usernames=["admin", "user", "guest", "operator"],
  passwords=["Password1", "Summer2024", "Welcome1"],
  delay_seconds=5
)
```

### Spray Passwords (High Success Rate)
These passwords satisfy common complexity requirements (upper + lower + number):
- `Password1`, `Password123`
- `Welcome1`, `Welcome123`
- `[Season][Year]` — `Summer2024`, `Winter2024`, `Spring2025`
- `[Company]1`, `[Company]123`
- `Changeme1`, `Changeme123`
- `Admin123`, `Admin1234`
- `Qwerty123`, `Letmein1`

### Rate Limiting and Lockout Avoidance
- **CRITICAL**: determine lockout policy BEFORE spraying
  - Try 2-3 known-wrong passwords on a test account to gauge lockout threshold
  - Common thresholds: 3, 5, or 10 failed attempts
- **Delay between attempts**: minimum 5 seconds, ideally 30-60 seconds
- **One password per account per spray round**: test one password across all users, wait, then next password
- **Never exceed**: (lockout threshold - 2) attempts per account per lockout window
- **Track attempts**: maintain count per username to prevent accidental lockout
- **Time lockout windows**: typically 15-30 minutes; spray one password, wait for window reset

### User Enumeration Techniques
Before spraying, identify valid usernames:
- Error message differences ("Invalid username" vs "Invalid password")
- Response time differences (valid users take longer due to password hash comparison)
- Account registration / password reset flows
- LDAP/AD enumeration if accessible
- Email format from OSINT (first.last@company.com)

## Phase 3: Credential Reuse and Lateral Movement

### Testing Credential Reuse
When you have a working credential pair:
1. **Same creds on other services** — test against SSH, RDP, VPN, web apps on other in-scope hosts
2. **Same password, different usernames** — people reuse passwords across personal/work accounts
3. **Password pattern variation** — if user uses `Password1` on one service, try `Password2`, `Password1!`, `password1`

### Lateral Movement Priority
After obtaining valid credentials:
1. SSH / Telnet on other hosts
2. Web management interfaces (routers, switches, firewalls)
3. Database connections
4. Cloud consoles (if cloud assets are in scope)
5. VPN / remote access
6. File shares (SMB, NFS)

### Privilege Escalation from Credentials
- Check if credential grants admin/root access
- Check sudo permissions for the user
- Look for credential files readable by the user (.env, config files, SSH keys)
- Check for password reuse between service accounts and admin accounts

## Phase 4: OSINT for Credentials

### Shodan Searches
- `hostname:target.com default password` — devices with known defaults
- `http.title:"login" org:"Target Corp"` — exposed login pages
- `port:23 org:"Target Corp"` — exposed telnet (often has default creds)
- `port:3389 org:"Target Corp"` — exposed RDP
- `"default password" product:"Apache httpd"` — servers with default configs

### GitHub / Code Repository Leaks
Search for:
- `org:targetcorp password`
- `org:targetcorp secret`
- `org:targetcorp api_key`
- `"target.com" password filename:.env`
- `"target.com" password filename:config`
- Tools: truffleHog, git-secrets, gitleaks

### Cloud Misconfigurations
- Public S3 buckets: `s3.amazonaws.com/target` or `target.s3.amazonaws.com`
- Public Azure blobs: `target.blob.core.windows.net`
- Public GCS buckets: `storage.googleapis.com/target`
- Exposed .env files: `https://target.com/.env`
- Exposed .git directories: `https://target.com/.git/config`

### Breach Databases (Authorized Use Only)
- Check if target domain appears in known breaches
- Use only with explicit engagement authorization
- Tools: HaveIBeenPwned API (commercial), DeHashed (commercial)
- NEVER access stolen credential databases directly

## Phase 5: Escalation Decision Tree

```
START
  │
  ├─ Try default credentials for identified device/service
  │   ├─ SUCCESS → Document finding (CRITICAL severity), test credential reuse
  │   └─ FAIL ↓
  │
  ├─ Enumerate users
  │   ├─ Users found → Password spray (respect lockout!)
  │   │   ├─ SUCCESS → Document, test reuse, attempt lateral movement
  │   │   └─ FAIL ↓
  │   └─ No users found ↓
  │
  ├─ OSINT reconnaissance
  │   ├─ Credentials found → Validate against target
  │   │   ├─ SUCCESS → Document, test reuse
  │   │   └─ FAIL ↓
  │   └─ No credentials found ↓
  │
  └─ Report: credential testing exhausted, recommend other vectors
```

## Findings Severity Guide

| Finding | CVSS Score | Severity |
|---------|------------|----------|
| Default admin credentials on internet-facing service | 9.8 | CRITICAL |
| Default credentials on internal service | 8.1 | HIGH |
| Weak password discovered via spraying | 7.5 | HIGH |
| Credential reuse across services | 7.2 | HIGH |
| Credentials found in public code repo | 8.6 | HIGH-CRITICAL |
| User enumeration possible | 5.3 | MEDIUM |
| No account lockout policy | 5.3 | MEDIUM |
| Exposed login page (no creds found) | 3.1 | LOW |

## Operational Notes

- **Always document authorization** before any credential testing
- **Never store plaintext passwords** in findings — use redacted format: `admin:P*****1`
- **Track all login attempts** with timestamps for the audit trail
- **Stop immediately** if you trigger account lockouts on accounts you didn't intend to lock
- **Respect scope** — do not test credentials against out-of-scope systems even if you believe they would work
- **Time sensitivity** — report default credentials immediately, not just in the final report
