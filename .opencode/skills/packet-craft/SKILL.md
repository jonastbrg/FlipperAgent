---
name: packet-craft
description: "Craft, send, and analyze network packets via Scapy — ARP scan, ping, traceroute, DNS, sniff, pcap analysis"
---

# Scapy Packet Crafting and Analysis

Run Scapy commands via Python one-liners in Bash. Requires `scapy` installed (`pip install scapy`). Some operations (ARP scan, sniffing) require root/sudo.

## ARP scan

Discover devices on a local network by sending ARP requests. Returns IP and MAC address pairs.

```bash
sudo python3 -c "
from scapy.all import ARP, Ether, srp
pkt = Ether(dst='ff:ff:ff:ff:ff:ff')/ARP(pdst='192.168.1.0/24')
ans, _ = srp(pkt, timeout=3, verbose=False)
print(f'ARP scan: {len(ans)} host(s) found')
for r in ans:
    print(f'  {r[1].psrc} -> {r[1].hwsrc}')
"
```

Adjust `timeout=` for slower networks (default 3 seconds). Change the CIDR to target the desired subnet.

## ICMP ping

Check if a host is alive using ICMP echo requests.

```bash
sudo python3 -c "
from scapy.all import IP, ICMP, sr1
target = '192.168.1.1'
count = 3
for i in range(count):
    reply = sr1(IP(dst=target)/ICMP(), timeout=2, verbose=False)
    if reply:
        print(f'Reply from {reply.src}: ttl={reply.ttl}')
    else:
        print('Request timed out')
"
```

## Traceroute

Trace the network path to a target by incrementing TTL.

```bash
sudo python3 -c "
from scapy.all import IP, ICMP, sr1
target = '8.8.8.8'
max_ttl = 20
print(f'Traceroute to {target}:')
for ttl in range(1, max_ttl + 1):
    reply = sr1(IP(dst=target, ttl=ttl)/ICMP(), timeout=2, verbose=False)
    if reply:
        print(f'  {ttl}: {reply.src}')
        if reply.src == target:
            break
    else:
        print(f'  {ttl}: * * *')
"
```

## DNS query

Perform DNS lookups using Scapy (bypasses system resolver). Supports A, AAAA, MX, TXT, NS, etc.

```bash
sudo python3 -c "
from scapy.all import IP, UDP, DNS, DNSQR, sr1
domain = 'example.com'
qtype = 'A'
pkt = IP(dst='8.8.8.8')/UDP(dport=53)/DNS(rd=1, qd=DNSQR(qname=domain, qtype=qtype))
reply = sr1(pkt, timeout=3, verbose=False)
if reply and reply.haslayer(DNS):
    print(f'DNS {qtype} {domain}:')
    for i in range(reply[DNS].ancount):
        rr = reply[DNS].an[i] if reply[DNS].ancount > 1 else reply[DNS].an
        print(f'  {rr.rrname.decode()} -> {rr.rdata}')
        if reply[DNS].ancount == 1:
            break
else:
    print('No DNS response')
"
```

## Sniff packets

Capture network packets on an interface for a short duration.

```bash
sudo python3 -c "
from scapy.all import sniff
# Adjust: iface='en0', count=20, timeout=5, filter='tcp port 80'
pkts = sniff(count=20, timeout=5, verbose=False)
print(f'Captured {len(pkts)} packets:')
for p in pkts:
    print(f'  {p.summary()}')
"
```

Optional BPF filter examples:
- `filter='tcp port 80'` -- HTTP traffic only
- `filter='udp'` -- UDP traffic only
- `filter='arp'` -- ARP traffic only
- `filter='host 192.168.1.1'` -- traffic to/from specific host

To capture on a specific interface, add `iface='en0'` (or `wlan0` on Linux).

## Analyze pcap file

Read and summarize a captured pcap/pcapng file.

```bash
python3 -c "
from scapy.all import rdpcap
pkts = rdpcap('capture.pcap')
print(f'Total packets: {len(pkts)}')
protocols = {}
for p in pkts[:50]:
    proto = p.lastlayer().__class__.__name__
    protocols[proto] = protocols.get(proto, 0) + 1
print('Protocol breakdown:')
for proto, count in sorted(protocols.items(), key=lambda x: -x[1]):
    print(f'  {proto}: {count} packets')
"
```

## Notes

- ARP scan and sniffing are MEDIUM risk -- they interact with the local network.
- Ping, traceroute, DNS query are LOW risk -- standard network diagnostics.
- PCAP analysis is LOW risk -- offline file reading.
- Most packet-sending operations require `sudo` on macOS/Linux.
- Scapy suppresses verbose output with `verbose=False` to keep output clean.
