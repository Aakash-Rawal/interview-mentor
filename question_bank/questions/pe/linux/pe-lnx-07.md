---
id: pe-lnx-07
domain: pe
topic: linux
difficulty: hard
tags: [networking, sockets, conntrack]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A busy proxy starts failing new outbound connections with EADDRNOTAVAIL. Explain what is happening at the kernel level and how to fix it short- and long-term.

## What interviewers look for
- Explains the failing syscall and the 4-tuple uniqueness rule, not just 'ran out of ports'
- Measures before tuning: counts TIME_WAIT, checks the configured range, checks per-destination distribution
- Knows the semantic difference between tcp_tw_reuse and tcp_tw_recycle and why one is dangerous
- Ranks fixes by durability — connection reuse beats kernel knobs
- States how they'd verify each change actually took effect

## Strong answer covers
1. EADDRNOTAVAIL comes from bind/connect when the kernel can't find a free ephemeral port for the (src IP, src port, dst IP, dst port) tuple; the 4-tuple must be unique, so the limit is per-destination, not global — 60k connections to one backend IP:port exhausts it, spread across many destinations does not
2. TIME_WAIT: the active closer holds the tuple for 2*MSL, 60s hardcoded on Linux (TCP_TIMEWAIT_LEN), to absorb delayed duplicate segments and ensure the final ACK — so ~1000 conn/s to one backend needs ~60k tuples in flight
3. Measurement: `ss -s` summary, `ss -tan state time-wait | wc -l`, `ss -tan state time-wait dst <backend>` to see concentration, `cat /proc/sys/net/ipv4/ip_local_port_range` (default often 32768-60999 = ~28k), `nstat -az | grep -i -E 'TcpExt|PortFail'`, and `netstat -s`/`nstat` counters like TcpExtTCPTimeWaitOverflow
4. Short-term: widen `net.ipv4.ip_local_port_range` to e.g. 1024-65535 (minding reserved ports and `ip_local_reserved_ports`), enable `net.ipv4.tcp_tw_reuse=1` which lets the initiator reuse a TIME_WAIT tuple for a new outbound connection when timestamps show it's safe (requires tcp_timestamps), and add more source IPs / bind-to-multiple-addresses or additional backend IPs to multiply the tuple space
5. Explicitly warns that `tcp_tw_recycle` is dangerous with NAT'd clients and was removed in kernel 4.12; and that lowering FIN timeouts (`tcp_fin_timeout` affects FIN_WAIT_2, not TIME_WAIT) is often misapplied
6. Long-term real fix: HTTP keep-alive / connection pooling to upstreams so you stop creating a connection per request, tune pool size and idle timeout, make the server the active closer so TIME_WAIT lands on the backend, use SO_REUSEADDR appropriately, or use a unix socket / mesh sidecar for local hops
7. Verification: `sysctl -w` for immediate effect plus /etc/sysctl.d for persistence, re-check `ss -s` and the connection rate, confirm error rate drops, and note that widening the range only buys headroom proportional to the increase
8. Fleet prevention: push the sysctl via config management, alert on TIME_WAIT count and ephemeral port utilisation as a percentage of the range, and dashboard connections-per-request as a proxy for missing keep-alive

## Follow-ups
- You widen the range and enable tw_reuse and it still fails. What's the next hypothesis?
- Why is tcp_tw_recycle unsafe, and what replaced it?
- How does the picture change if the proxy is behind a NAT gateway or using a single SNAT IP?
- How would you prove that enabling keep-alive actually reduced connection churn?

## Sample answer
EADDRNOTAVAIL means connect() couldn't find a free source port. The kernel needs the 4-tuple — source IP, source port, dest IP, dest port — to be unique, so the limit is per-destination. If this proxy is hammering one backend IP and port, it's bounded by the ephemeral range, typically 32768–60999, about 28,000 ports, and every closed connection where we were the active closer sits in TIME_WAIT for 60 seconds. So roughly 470 new connections per second to a single backend is enough to exhaust it. I'd measure first: `ss -s`, `ss -tan state time-wait | wc -l`, break it down by destination, check `cat /proc/sys/net/ipv4/ip_local_port_range`, and look at nstat counters. Short term I'd widen the range to 1024–65535 and set `net.ipv4.tcp_tw_reuse=1`, which lets the initiator safely reuse a TIME_WAIT tuple using TCP timestamps — I'd explicitly not touch tcp_tw_recycle, which breaks NAT'd clients and was removed in 4.12. Adding source IPs or backend IPs multiplies the tuple space too. But the real fix is upstream: turn on HTTP keep-alive and connection pooling so we aren't opening a socket per request, and ideally let the server be the active closer so TIME_WAIT lands on their side. I'd apply sysctls via /etc/sysctl.d through config management, verify with ss and the error rate, and alert on port-range utilisation fleet-wide.
