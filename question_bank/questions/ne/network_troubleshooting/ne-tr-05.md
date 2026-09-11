---
id: ne-tr-05
domain: ne
topic: network_troubleshooting
difficulty: hard
tags: [asymmetric, stateful]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
After adding a second uplink for redundancy, some long-lived connections start dropping randomly. Nothing is 'down'. What is happening?

## What interviewers look for
- Connects 'nothing is down' plus 'only long-lived flows' to statefulness rather than hunting for a broken link
- Proves asymmetry with evidence from both paths before proposing a fix
- Distinguishes idle-timeout drops from state-miss drops
- Weighs several fixes and picks one based on the actual topology and blast radius
- Thinks about what else in the path is stateful besides the obvious firewall

## Strong answer covers
1. Reads the clues correctly: new redundant path + no link/interface alarms + only long-lived or idle-then-resumed sessions dying = state loss on a stateful device, not forwarding loss; short-lived connections succeed because they complete before the path changes
2. Hypothesis: routing is now asymmetric or the ECMP hash re-pins flows so the forward path traverses firewall/NAT A while the return traverses B, which has no session entry and silently drops or sends a RST
3. Proof from both ends: simultaneous captures at the client and server for the failing five-tuple — packets leave one side and never arrive, or a RST appears — plus captures/logs on both firewalls; firewall logs showing 'no session match', 'invalid TCP non-SYN', or out-of-state drops; conntrack table lookups on each node
4. Confirms the path with traceroute in both directions for that specific flow and by inspecting the actual route/ECMP selection (`ip route get <dst> from <src> sport/dport`, `show ip cef exact-route`, per-flow hash), and checks whether a route was preferred/added at the moment sessions started dropping
5. Rules in/out the adjacent look-alikes: firewall/NAT idle timeout shorter than the application's keepalive interval, conntrack table full (`nf_conntrack_count` vs max, dropped-entry counters), uRPF/rp_filter drops on the asymmetric return, route flap causing path change mid-session, and LACP/ECMP rehash on member add
6. Enumerates fixes with trade-offs: force symmetry with routing policy (local-pref/MED/metrics/PBR so a prefix uses one path), active/standby rather than active/active for the stateful pair, state synchronisation between firewalls (HA session sync, conntrackd) noting it needs a sync link and identical config, symmetric/consistent hashing on the load-sharing device, or remove statefulness from that path entirely (stateless ACLs, route the path around the firewall)
7. Mitigation with small blast radius while diagnosing: cost out or drain the new uplink so traffic is symmetric again, verify long-lived sessions stop dropping, then re-introduce it deliberately with the chosen fix
8. Verification and prevention: re-run the exact long-lived test (a session held idle past the timeout, or a long transfer) and watch the same captures; prevention is a rule that stateful devices are never placed on asymmetric-capable paths without state sync, TCP keepalives below the firewall idle timeout, out-of-state drop alerting, and testing failover/second-path scenarios in a lab before adding redundancy

## Follow-ups
- How do you distinguish an asymmetric-path state miss from a firewall idle timeout expiring? Be specific about what you'd see in the capture.
- The firewalls support state sync but it's not enabled. What are the risks of turning it on in production, and what do you check first?
- Your design must stay active/active for capacity reasons. How do you guarantee symmetry per flow?
- The same symptom appears with a stateful NAT in the cloud where you can't see the device. What evidence do you gather instead?

## Sample answer
Nothing down, only long-lived sessions dying, and it started when a second path appeared — that's a state problem, not a forwarding problem. The likely story is that the forward path now goes through one stateful device and the return path through the other, so the second one sees a mid-stream ACK with no session and drops it or RSTs it. Short connections survive because they finish before the path changes. I prove it rather than assume it: captures on client and server for one failing five-tuple, so I can say packets left here and never arrived there, plus firewall logs looking for out-of-state or no-session-match drops and a conntrack lookup on each node. I confirm the path per flow with route-get or exact-route in both directions, and I check whether uRPF is also dropping the return. I also rule out the cheap alternative, a firewall idle timeout shorter than the app's keepalive. To stop the bleeding I drain the new uplink so traffic is symmetric again and verify sessions stabilise. Then the real fix, by topology: routing policy or PBR to pin prefixes to one path, active/standby instead of active/active, enable HA session sync, or take the stateful device out of that path. Verify with the same long-held session, and set TCP keepalives below the firewall timeout.
