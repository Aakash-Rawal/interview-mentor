# Network Troubleshooting (Network Engineering)

## Methodology — isolate by layer
Pick bottom-up or split-half, then narrow. State which layer you're testing and why.

## Tool → symptom map
| Tool | Answers | Notes |
|---|---|---|
| `ping` | L3 reachability + RTT | ICMP may be filtered; absence ≠ down |
| `traceroute` / `mtr` | per-hop path + loss | `mtr` shows sustained loss per hop |
| `dig` / `nslookup` | DNS resolution | test authoritative vs resolver |
| `tcpdump` / Wireshark | actual packets | confirm handshake, retransmits, resets |
| `ss -tunap` | sockets/listeners | is the service even listening? |
| `ip route get <ip>` | which route wins | next-hop + egress interface |
| `ethtool` | link/speed/duplex/errors | physical + NIC counters |
| `curl -v` | L7 + TLS handshake | separates app from network |

## Reading signals correctly
- **Loss at one hop only** in mtr but fine after = that hop deprioritises ICMP (not the problem).
- **Loss that persists to the destination** = real path loss.
- **High RTT increasing with hops** = distance/congestion; sudden jump = a slow link.
- **SYN sent, no SYN-ACK** = firewall/ACL drop or nothing listening.
- **RST** = port closed or app rejected.
- **Asymmetric routing** = forward and return paths differ; breaks stateful firewalls.

## Classic multi-layer root causes
- BGP session flap → route withdrawal → intermittent reachability.
- PMTU black hole → small packets fine, large transfers hang.
- Duplicate IP / ARP conflict → intermittent connectivity that moves around.
- MTU mismatch across a trunk → fragmentation or drops.
- DNS resolves to a stale/region-wrong IP → "site slow" that's really routing.

## Behaviour (scored)
Layer isolation · right tool for the symptom · correct protocol explanation ·
blast-radius awareness before changes · precise root cause · fix + monitoring to prevent recurrence.
