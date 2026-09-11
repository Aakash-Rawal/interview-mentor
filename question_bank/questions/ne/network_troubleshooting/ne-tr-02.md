---
id: ne-tr-02
domain: ne
topic: network_troubleshooting
difficulty: medium
tags: [tcp, firewall, tcpdump]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A client gets connection timeouts to a service that's confirmed up and listening. tcpdump on the client shows SYN sent, no SYN-ACK. What are the possibilities and how do you tell them apart?

## What interviewers look for
- Immediately proposes capturing at the far end rather than reasoning only from the client's view
- Enumerates the candidate causes as a decision tree with a distinguishing observation for each
- Knows what a RST versus silence versus ICMP unreachable tells you
- Thinks about return-path/stateful-device failure modes, not just inbound filtering
- Verifies with the exact failing five-tuple, not a generic ping

## Strong answer covers
1. Establishes the exact failing five-tuple first: client IP:ephemeral port → server IP:port, protocol, and confirms the server listens on that address specifically (`ss -ltnp` showing 0.0.0.0:443 vs 127.0.0.1:443)
2. Runs a simultaneous capture on the server filtered to the pair, e.g. `tcpdump -ni any host <client> and port <p> and 'tcp[tcpflags] & tcp-syn != 0'`, and states that the capture is the arbiter
3. Case 1 — SYN never reaches the server: dropped in transit by an ACL, security group/NACL, stateful firewall, or a routing black hole; narrows by bisecting the path (test from a midpoint host/jump box), checking ACL hit counters and `ip route get`/`show ip route` for the destination
4. Case 2 — SYN arrives, no SYN-ACK leaves: host firewall (iptables/nftables INPUT drop, firewalld), nothing bound on that interface/IP, listen backlog full (`ss -ltn` Recv-Q at the backlog limit, `netstat -s` / `nstat` SYNs-to-LISTEN-sockets-dropped, tcp_syn overflow counters), SYN cookies, or a container/namespace binding mismatch
5. Case 3 — SYN-ACK is sent but the client never sees it: asymmetric return path through a stateful firewall or NAT with no matching state, reverse-path filtering (rp_filter) or uRPF drop, wrong default route/source-based routing on a multi-homed server, or the SYN-ACK going out an interface that's blocked
6. Case 4 — client-side loss/misconfiguration: SYN never actually leaves the NIC (check capture on the client egress interface), local firewall OUTPUT rule, MTU is irrelevant here since a SYN is small — explicitly rules MTU out for SYN failures
7. Contrasts silence with a RST (active refusal: closed port, firewall reject rule, or a middlebox/load balancer with no backend) and with ICMP admin-prohibited/host-unreachable, which names the filtering device
8. Verification and prevention: re-run the same connection test after each change (`nc -zv` or curl to the same port), keep captures from both ends as evidence; prevention includes reachability synthetic checks per service port, ACL/security-group change review, and BFD/symmetry policy on redundant paths

## Follow-ups
- The server capture shows the SYN arriving and a SYN-ACK going out, and the client sees nothing. Give me three concrete ways to prove which device is eating it.
- Same symptom but it only fails for about one in five connection attempts. What changes in your approach?
- How does this diagnosis differ for UDP, where there's no handshake to watch?
- The service is behind a load balancer and a NAT. Where exactly do you capture, and what does the five-tuple look like at each point?

## Sample answer
I need the exact pair — client IP and source port to server IP and port — and I confirm the server is listening on that address, not just on loopback. Then the key move: capture on the server at the same time as the client, filtered to that pair, SYN flag set. That splits it into four worlds. If the SYN never arrives, it's dropped in transit — ACL, security group, stateful firewall, or a black-holed route — and I bisect, testing from a host midway and checking ACL hit counters and the route for the destination. If the SYN arrives and no SYN-ACK leaves, it's the host: nftables INPUT drop, nothing bound on that interface, or the listen backlog is full, which I confirm with ss Recv-Q and the SYN-drop counters in nstat. If the SYN-ACK goes out but the client never sees it, that's the interesting one: asymmetric return path hitting a stateful firewall or NAT with no state, rp_filter or uRPF dropping it, or the wrong default route on a multi-homed box. And I note a RST would mean something actively refused — closed port or a reject rule — not a drop. MTU isn't a candidate; SYNs are tiny. Then I re-run the same nc test to verify.
