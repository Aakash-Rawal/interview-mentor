---
id: ne-rt-01
domain: ne
topic: routing
difficulty: hard
tags: [bgp, convergence, failure-analysis, bfd]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Walk me through exactly what happens when an eBGP session drops, end to end, from the first missed keepalive to traffic flowing on the new path.

## What interviewers look for
- Narrates the lifecycle in ordered phases with real timer numbers rather than a vague 'it reconverges'
- Separates control-plane convergence from data-plane (FIB) programming and knows the latter often dominates
- Quantifies blast radius: which prefixes, which peers, how much traffic shifts where
- Volunteers the fast-detection and damage-limiting mechanisms (BFD, GR/LLGR, dampening) and their trade-offs
- Thinks about the downstream/neighbour-AS view, not just the local router

## Strong answer covers
1. Detection: default keepalive 60 s / hold 180 s (negotiated to the lower of the two), so worst case ~3 minutes of blackholing before teardown
2. Faster detection paths: BFD (e.g. 300 ms x 3 ≈ 900 ms), fast-external-fallover for directly-connected peers where interface-down tears the session immediately, and that a soft failure (one-way path) only gets caught by hold expiry or BFD
3. Teardown mechanics: NOTIFICATION sent if the local side initiates, TCP/179 session closed, state returns to Idle, all paths from that peer flushed from Adj-RIB-In
4. Best-path re-run for every affected prefix; alternate paths promoted per the selection order; withdrawals or replacement UPDATEs sent to remaining eBGP and iBGP peers
5. RIB update then FIB/hardware programming — with a full table (~1M routes) this can take seconds to tens of seconds; convergence is not instantaneous even after the control plane settles
6. Downstream propagation AS by AS, MRAI/advertisement-interval batching (~30 s eBGP default on some platforms), and route-flap dampening potentially suppressing a flapping prefix
7. Graceful restart / LLGR preserve forwarding across a control-plane restart, and why you must distinguish a control-plane restart from a real link failure before enabling it
8. Blast radius stated concretely: every prefix learned over that peer, all traffic destined to those prefixes plus the return path, and whether an alternate exit has capacity

## Follow-ups
- Now run the same failure with BFD at 300 ms x 3 and graceful restart enabled — what changes, and what new failure mode have you introduced?
- The alternate exit only has 40% of the capacity of the failed one. How do you plan for that, and what would you pre-configure so the failover doesn't cause congestion?
- The session flaps every 90 seconds instead of staying down. How do you triage that, and would you enable dampening?
- How does this timeline differ for an iBGP session over a route reflector versus a directly-connected eBGP peer?

## Sample answer
Detection first. With defaults, keepalives are 60 seconds and hold is 180, negotiated to the lower of the two, so if it's a silent failure I can blackhole for up to three minutes. If the peer is directly connected and the interface drops, fast external fallover tears it down immediately; with BFD at 300 ms times three I detect in under a second. Then teardown: NOTIFICATION if we initiate, the TCP session on port 179 closes, state goes back to Idle, and every path from that peer is flushed from the Adj-RIB-In. Best path re-runs for each affected prefix; alternates get promoted, and we send withdrawals or replacement UPDATEs to our other peers. That hits the RIB, then the FIB — on a full table that hardware programming is often the slow part, seconds to tens of seconds, not microseconds. Downstream, withdrawals propagate AS by AS, batched by MRAI, and if the prefix flaps someone may dampen it. Graceful restart or LLGR would keep forwarding through a control-plane restart, but it's actively harmful if the failure is a real data-plane outage. Blast radius is everything learned over that peer — so I'd check how many prefixes and how much traffic, and whether the alternate exit has capacity for the shift.
