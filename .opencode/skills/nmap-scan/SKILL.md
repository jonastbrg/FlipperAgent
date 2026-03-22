---
name: nmap-scan
description: "Network scanning via nmap — host discovery, port scanning, service/OS detection, vulnerability scanning"
---

# Nmap Network Scanning

Run nmap directly via Bash. Requires `nmap` installed (`brew install nmap` on macOS).

## Input validation

Before running any nmap command, validate the target to prevent command injection:

- **Valid targets:** IPs (`192.168.1.1`), hostnames (`example.com`), CIDRs (`192.168.1.0/24`), comma-separated lists (`192.168.1.1,192.168.1.2`)
- **Target regex:** Must match `^[\w\.\-\,\/\:]+$` -- only word chars, dots, hyphens, commas, slashes, colons
- **Port regex:** Must match `^[\d,\-]+$` -- only digits, commas, hyphens
- **Never** pass unsanitized user input directly into the nmap command string

## Quick scan

Find open ports and services. Fast (T4 timing), shows only open ports.

```bash
nmap -T4 --open 192.168.1.0/24
```

With specific ports:

```bash
nmap -T4 --open -p 22,80,443,8080 192.168.1.1
```

## Service/version scan

Deep scan that detects service versions and attempts OS fingerprinting. Slower but more detailed.

```bash
nmap -sV -O -T4 192.168.1.1
```

With specific ports:

```bash
nmap -sV -O -T4 -p 1-1000 192.168.1.1
```

## Host discovery (ping sweep)

Find live hosts on a network without port scanning.

```bash
nmap -sn 192.168.1.0/24
```

## Vulnerability scan

Scan for known vulnerabilities using nmap's built-in NSE vuln scripts.

```bash
nmap --script vuln -T4 192.168.1.1
```

With specific ports:

```bash
nmap --script vuln -T4 -p 80,443 192.168.1.1
```

## Parsing nmap output

For structured output, use the `-oX -` flag and parse XML, or use the `python-nmap` library:

```bash
python3 -c "
import nmap
scanner = nmap.PortScanner()
scanner.scan('TARGET', arguments='-sV -T4')
for host in scanner.all_hosts():
    print(f'{host} ({scanner[host].hostname()}) - {scanner[host].state()}')
    for proto in scanner[host].all_protocols():
        for port in sorted(scanner[host][proto].keys()):
            info = scanner[host][proto][port]
            print(f'  {port}/{proto} {info[\"state\"]} {info.get(\"name\",\"?\")} {info.get(\"product\",\"\")} {info.get(\"version\",\"\")}')
"
```

## Notes

- Host discovery (`-sn`) is LOW risk -- no port scanning, just pings.
- Quick scan and service scan are MEDIUM risk -- active probing.
- Vuln scan is MEDIUM risk -- runs NSE scripts against open services.
- On macOS, some scans (SYN scan `-sS`, OS detection `-O`) require `sudo`.
- Default scan (no `-p`) checks the top 1000 most common ports.
- Use `-p-` to scan all 65535 ports (slow).
- T4 timing is aggressive but safe for LAN. Use T3 for WAN to avoid detection.
