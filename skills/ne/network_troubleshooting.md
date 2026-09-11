# Network Troubleshooting — Network Engineering

## What this interview actually tests
Layered isolation with evidence. The interviewer plays the network: you name the check, they
give output, you interpret and narrow. Scored on layer isolation, tool selection, protocol
knowledge, blast-radius awareness, root-cause precision, and fix-plus-prevention. "It works
sometimes" scenarios are common — bring a method for intermittent faults.

## The method (say it, then do it)
1. **Define the failure** — who, to what, since when, always or intermittent, what error.
   Get a specific failing pair: source IP/port → destination IP/port, protocol.
2. **What changed** — config pushes, links, optics, routes, ACLs, DNS, cert, MTU, new host.
3. **Isolate by layer, bottom-up or divide-and-conquer**: physical → L2 → L3 → L4 → app.
   Bisect the path: test from the midpoint.
4. **Capture on both ends** when packets "disappear" — `tcpdump` is the arbiter.
5. **Mitigate with the smallest blast radius** (drain a link, withdraw a route, roll back
   an ACL) before the root-cause hunt if users are hurting.
6. **Fix, verify with the same test that showed the failure, prevent.**

## Layer checklist
| Layer | Check | Tools / signals |
|---|---|---|
| Physical | link up? errors? light levels? speed/duplex? | interface counters (CRC, input errors, output drops), `ethtool -S`, optic DOM |
| L2 | VLAN correct on both ends? trunk allows it? MAC learned? STP state? | `show mac address-table`, `show vlan`, `show spanning-tree`, MAC flap logs |
| L3 | route present? next-hop reachable? ARP/ND resolved? ACL? | `ip route get`, `show ip route`, `ip neigh`, `traceroute`, ACL hit counts |
| L4 | port listening? firewall state? NAT entry? | `ss -ltnp`, `nc -zv`, `tcpdump 'tcp[tcpflags] & syn != 0'`, conntrack table |
| App | DNS answer correct? TLS ok? app healthy? | `dig`, `openssl s_client`, `curl -v`, app logs |

## Reading the classic captures
- **SYN out, nothing back**: dropped in transit or on the host. Capture at the server: SYN
  never arrives → firewall/ACL/security group/route black hole between. SYN arrives, no
  SYN-ACK → host firewall, nothing listening on that address, backlog full. SYN-ACK sent but
  client never sees it → **asymmetric return path** through a stateful device, or reverse-
  path filtering.
- **RST**: something actively refused — closed port, firewall reject, or a middlebox.
- **Retransmissions / dup ACKs**: loss on the path; correlate with interface errors.
- **ICMP frag-needed missing + hangs on large payloads**: PMTUD black hole → MSS clamp.
- **Duplicate packets / TTL changes mid-session**: loop or path flap.

## Intermittent and "one region" problems
- `mtr` from both directions, long run (`-c 500`), compare per-hop loss; loss that does not
  persist to the final hop is ICMP deprioritisation, not real loss.
- Correlate with BGP events (`show bgp neighbor ... flap`, route-change logs), link flaps,
  microbursts (interface drops with low average utilisation), ECMP polarisation (one path bad
  → subset of flows bad; vary source port to find it).
- Asymmetry after adding redundancy: forward and return paths differ → stateful firewalls/NAT
  drop mid-session. Force symmetry, sync state, or remove statefulness.
- DHCP failures in one rack: scope exhaustion, relay/helper on the new SVI, DHCP snooping
  trust on the ToR, VLAN missing on the trunk. Capture DISCOVER/OFFER at the relay.
- Slow, not broken: check duplex mismatch, small-buffer congestion, BDP for long-haul,
  packet loss even at 0.1%, DNS delays (try the IP directly).

## Blast-radius reflexes
- Before shutting a link: what rides it? Is there an ECMP/LACP sibling? Drain first
  (cost-out, `shutdown` after traffic moves).
- Before touching BGP: how many prefixes, which peers, what's the fallback path?
- Before an ACL change: hit counters, ordering, a reversible push, a canary device.
- Announce changes; have the rollback typed before you apply.

## Prevention vocabulary
Interface error alerting (CRC rate, not just link state), optic DOM thresholds, BFD on
all routed links, MSS clamping standard on tunnels, config diff review + lab test, storm
control/BPDU guard on access ports, RPKI + prefix filters at the edge, synthetic probes
between sites, capture-on-demand tooling.

## Common mistakes
- Starting at L7 ("check the app") when a counter would have shown CRC errors in seconds.
- Capturing on one end only and concluding "the network ate it".
- Treating mtr intermediate-hop loss as real loss.
- Fixing the symptom on one device without asking why the topology allowed it.
- No verification step: "I changed the MSS" without re-running the failing transfer.

## Practice prompts
- One region intermittently slow; other regions fine.
- SYN no SYN-ACK: distinguish four causes with captures.
- 0.5% loss on an inter-switch link: optic, fibre, port, or congestion?
- New second uplink → long-lived sessions drop randomly.
- Pod-wide CPU spike on all switches after cabling a new one.
