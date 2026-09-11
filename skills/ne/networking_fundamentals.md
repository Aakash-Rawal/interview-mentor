# Networking Fundamentals — Network Engineering

## What this interview actually tests
Whether your mental model of the stack is correct and **layered**: can you say exactly what
happens at L2/L3/L4 for a packet, reason about addressing and MTU by hand, and apply it to
a symptom. Scored on conceptual accuracy, layer isolation, practical application, edge cases,
and clarity. "Explain end to end" and "why does X behave like that" dominate.

## The canonical walk-through: laptop loads https://example.com
1. **Link**: Wi-Fi association/auth → DHCP DISCOVER/OFFER/REQUEST/ACK (broadcast; relay if
   the server is off-subnet) → IP, mask, gateway, DNS, lease.
2. **DNS**: stub resolver → cache → recursive resolver (ISP/8.8.8.8) → root → .com TLD →
   authoritative → A/AAAA with TTL. Negative caching on NXDOMAIN.
3. **ARP** for the gateway MAC (host is off-subnet by mask comparison); ND for IPv6.
4. **TCP handshake**: SYN (ISN, MSS, window scale, SACK) → SYN-ACK → ACK. Ephemeral source
   port. NAT rewrites at the edge and keeps a state entry.
5. **TLS**: ClientHello with SNI + ALPN → ServerHello, cert, key exchange (ECDHE) → Finished.
   TLS 1.3 is 1-RTT. Cert chain validation, OCSP/CRL.
6. **HTTP** request → response; keep-alive reuses the connection; HTTP/2 multiplexes.
7. **Routing** hop by hop: each router does a longest-prefix match, decrements TTL, rewrites
   L2 headers; the L3 header is untouched except TTL/checksum (and NAT).
Strong candidates keep layers straight and say where each failure would show up.

## Addressing you must do in your head
- /24 = 256 addresses, 254 usable. /26 = 64/62. /27 = 32/30. /28 = 16/14. /30 = 4/2.
  /31 = 2 usable on point-to-point (RFC 3021, no broadcast) — preferred on modern gear.
- Usable = 2^(32-prefix) − 2 (network + broadcast) except /31 and /32.
- Block boundaries: /26 blocks start at .0/.64/.128/.192. Given 10.1.5.77/26 → network
  10.1.5.64, broadcast 10.1.5.127.
- RFC 1918: 10/8, 172.16/12, 192.168/16. Link-local 169.254/16. CGNAT 100.64/10.
- IPv6: /64 per LAN, /48 per site typical; SLAAC vs DHCPv6; ND replaces ARP; no broadcast.
- Summarisation: 10.1.0.0/24 … 10.1.3.0/24 → 10.1.0.0/22.

## Layer-2 essentials
- Switch learns source MACs, floods unknown unicast/broadcast within the VLAN.
- **VLAN** = broadcast domain; 802.1Q tag on trunks; native VLAN untagged; SVI routes
  between VLANs. Same-VLAN, can't ping → host firewall first, then ARP, port isolation, mask.
- **STP** blocks loops; a loop = broadcast storm, MAC flapping, CPU spike on every switch.
  BPDU guard on access ports, loop guard, storm control.
- **LACP/MLAG** for link redundancy; hashing per flow.
- ARP: who-has broadcast → reply unicast; gratuitous ARP on failover (VRRP/HSRP).

## Layer-3/4 essentials
- Longest-prefix match wins, then administrative distance across protocols, then metric.
- TTL decrement; traceroute exploits it (ICMP time-exceeded per hop; hops may
  deprioritise ICMP — loss that doesn't persist to the end isn't real loss).
- **MTU/PMTUD**: default 1500; tunnels/VXLAN/GRE/IPsec shave 20–70 bytes. DF-bit set + ICMP
  "fragmentation needed" blocked = **black hole**: small packets work, big transfers hang.
  Diagnose `ping -M do -s 1472`, `tracepath`; fix MSS clamping, allow ICMP type 3/4, jumbo end-to-end.
- **TCP**: 3-way handshake, sequence/ACK, retransmission (RTO, fast retransmit on 3 dup ACKs),
  flow control (receive window), congestion control (slow start, CUBIC/BBR, cwnd collapses on
  loss). Throughput ≤ window / RTT → **bandwidth-delay product**: 10 Gbps × 80 ms = 100 MB
  in flight needed; small buffers cap single flows. Mathis: throughput ∝ MSS / (RTT × √loss).
- **UDP**: no handshake, no retransmit; DNS, VoIP, QUIC (which reimplements reliability).
- **ICMP** types you'll name: 0/8 echo, 3 unreachable (code 4 = frag needed), 11 time exceeded.
- **NAT** types (source/destination/PAT), state timeouts, hairpinning, why it breaks
  inbound and some protocols (FTP, SIP).
- States: SYN sent no SYN-ACK = dropped (firewall/black hole); RST = actively refused;
  TIME_WAIT normal on the closer; many CLOSE_WAIT = app not closing sockets.

## DNS essentials
Recursive vs authoritative; A/AAAA/CNAME/MX/NS/SOA/TXT/PTR/SRV; TTL trade-off (failover speed
vs resilience/caching); if authoritatives die, cached answers survive until TTL expiry;
split-horizon; anycast resolvers; DNSSEC basics; `dig +trace`, `dig @server`.

## Tools and what they prove
`ping` (reachability + RTT), `traceroute`/`mtr` (path + per-hop loss), `ss`/`netstat`
(sockets/states), `tcpdump`/`wireshark` (what's actually on the wire — the arbiter),
`arp -a`/`ip neigh`, `ip route get`, `dig`, `iperf3` (throughput), `nc -zv` (port open?).

## Common mistakes
- Mixing layers ("the switch routes it"; "ARP for a remote host").
- Off-by-one on usable hosts; forgetting /31 exists.
- Blaming "the network" for a host firewall or an application not listening.
- Treating traceroute ICMP deprioritisation as loss.
- Not knowing BDP: "just add bandwidth" for a single-flow throughput problem.

## Practice prompts
- Hosts in a /26: 10.1.5.77 and 10.1.5.130 — same subnet? Show it.
- Large transfers hang across a new VPN; small ones fine.
- One 10 Gbps flow between DCs 80 ms apart gets 200 Mbps.
- SYN sent, no SYN-ACK vs RST: what does each tell you?
- Explain DHCP relay and what breaks when the helper address is wrong.
