---
name: shodan-recon
description: "Search Shodan for internet-connected devices, lookup IPs, find exploits — via Python shodan library"
---

# Shodan Reconnaissance

Use the Python `shodan` library via Bash to query the Shodan API. Requires `SHODAN_API_KEY` environment variable.

## Prerequisites

```bash
pip install shodan
```

The API key is read from `$SHODAN_API_KEY`. If not set, all commands will fail with an auth error.

## Search for devices

Find internet-connected devices matching a query. Supports Shodan query syntax: `port:22`, `country:US`, `product:Apache`, `city:Berlin`, `org:"Amazon"`, `os:"Linux"`, etc.

```bash
python3 -c "
import shodan, os
api = shodan.Shodan(os.environ['SHODAN_API_KEY'])
results = api.search('QUERY_HERE', limit=10)
print(f\"Total results: {results['total']}\")
for r in results['matches'][:10]:
    ip = r['ip_str']
    port = r['port']
    org = r.get('org', '?')
    product = r.get('product', '')
    country = r.get('location', {}).get('country_name', '?')
    vulns = ', '.join(r.get('vulns', {}).keys()) or 'none'
    print(f'{ip}:{port} | {org} | {product} | {country} | vulns: {vulns}')
"
```

Adjust `limit=` to control how many results are returned (default 10, max 100 for free tier).

## Host lookup

Get detailed information about a specific IP address: open ports, services, OS, vulnerabilities, hostnames.

```bash
python3 -c "
import shodan, os
api = shodan.Shodan(os.environ['SHODAN_API_KEY'])
info = api.host('TARGET_IP')
print(f\"IP: {info.get('ip_str', '?')}\")
print(f\"Organization: {info.get('org', '?')}\")
print(f\"OS: {info.get('os', '?')}\")
print(f\"Ports: {', '.join(str(p) for p in info.get('ports', []))}\")
print(f\"Hostnames: {', '.join(info.get('hostnames', []))}\")
vulns = info.get('vulns', [])
print(f\"Vulns: {', '.join(vulns) if vulns else 'none'}\")
print(f\"Last update: {info.get('last_update', '?')}\")
if info.get('data'):
    print(f\"Services ({len(info['data'])}):\" )
    for svc in info['data'][:5]:
        print(f\"  port {svc.get('port')}/{svc.get('transport','?')}: {svc.get('product', '?')} {svc.get('version', '')}\")
"
```

## Exploit search

Search for known exploits related to a product, CVE, or keyword.

```bash
python3 -c "
import shodan, os
api = shodan.Shodan(os.environ['SHODAN_API_KEY'])
results = api.exploits.search('QUERY_HERE', limit=5)
matches = results.get('matches', [])
if not matches:
    print('No exploits found')
else:
    print(f'Exploits ({len(matches)} results):')
    for e in matches:
        source = e.get('source', '?')
        desc = e.get('description', '?')[:120]
        print(f'  [{source}] {desc}')
        if e.get('cve'):
            print(f'    CVEs: {chr(44).join(e[\"cve\"])}')
"
```

## Get my public IP

```bash
python3 -c "
import shodan, os
api = shodan.Shodan(os.environ['SHODAN_API_KEY'])
print(f'Your public IP: {api.tools.myip()}')
"
```

## Notes

- All Shodan queries are read-only and LOW risk.
- Free API tier has rate limits (~1 query/second) and limited results.
- For large scans, consider `api.search_cursor()` for pagination.
- Common useful queries:
  - `webcam` -- internet-connected cameras
  - `port:23 default password` -- telnet with default creds
  - `product:Apache country:DE` -- Apache servers in Germany
  - `net:192.168.0.0/16` -- devices in a specific range
  - `has_screenshot:true` -- devices with screenshots
