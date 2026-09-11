---
id: ne-rt-05
domain: ne
topic: routing
difficulty: easy
tags: [bgp, ibgp, next-hop, route-reflector]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Routes learned via eBGP show up on an iBGP peer but are not installed in its routing table. What is the most common cause?

## What interviewers look for
- Names next-hop reachability immediately and explains the underlying rule, not just the fix
- Knows the exact verification step to confirm before changing config
- Compares the two legitimate fixes and picks one with a reason
- Understands route reflector behaviour and why RRs preserve the next-hop too
- Distinguishes 'in the BGP table but not best' from 'best but not installed'

## Strong answer covers
1. Rule: iBGP does not rewrite NEXT_HOP, so the eBGP peer's address (the external link) is carried unchanged to internal routers; if that address isn't in the IGP/RIB the path is invalid and never becomes best
2. Confirm with `show ip bgp <prefix>` — the path shows but is marked inaccessible / not `>`; then `show ip route <next-hop>` to prove the next-hop is unresolvable
3. Fix 1: `neighbor <peer> next-hop-self` on the border router's iBGP sessions (and `next-hop-self all` on a route reflector if you want it to rewrite for reflected routes)
4. Fix 2: carry the external link subnet in the IGP (passive interface or redistribute connected with a filter) — works but injects external addressing into your IGP and adds churn from a third party's link
5. Trade-off statement: next-hop-self is generally preferred; it keeps the IGP clean and makes the border router the forwarding attractor, at the cost of hiding per-link granularity and breaking some multipath/third-party-next-hop scenarios
6. Route reflection basics: RR preserves NEXT_HOP, AS_PATH and LOCAL_PREF by design, adds ORIGINATOR_ID and CLUSTER_LIST for loop prevention, and clients need no full mesh — the iBGP-learned-routes-are-not-re-advertised-to-iBGP rule is what the RR relaxes
7. Other causes to rule out: recursive resolution failing over a route that's itself invalid, a higher-AD source (e.g. static, OSPF at 110) beating iBGP at AD 200 for the same prefix, the prefix being filtered by an inbound policy on the iBGP peer, and legacy BGP synchronisation (long since disabled by default)
8. Mentions that BGP is only sent to peers if it's best, so a border router with an invalid next-hop won't even re-advertise the path onward

## Follow-ups
- You apply next-hop-self and the route installs, but now traffic is taking a suboptimal path inside your AS. Why could that be?
- In a route-reflector design, which router should set next-hop-self and why does it matter for the RR's own best-path?
- The next-hop resolves fine but the route still isn't installed and there's an OSPF route for the same prefix. Walk me through it.
- How would you monitor for next-hop-unreachable paths fleet-wide rather than discovering them during an incident?

## Sample answer
Almost always the next-hop is unreachable. iBGP doesn't rewrite NEXT_HOP, so the border router hands the internal peers the external link address of the eBGP neighbour. If that /30 or /31 isn't in the IGP, the internal router can't resolve it, the path is invalid, and it never becomes best — it sits in the BGP table without a caret. I'd confirm exactly that: `show ip bgp <prefix>` to see the path marked inaccessible, then `show ip route <next-hop>` to show there's no route. Two fixes. Set `next-hop-self` on the border router's iBGP sessions, which rewrites the next-hop to its own loopback — that's what I'd do, because the loopback is already in the IGP and I keep a third party's link addressing out of my IGP. Or advertise the external link subnet into the IGP as a passive interface, which works but adds external addressing and someone else's link flaps to my link-state database. On a route reflector you need `next-hop-self all` if you want it to rewrite for reflected routes, because an RR preserves next-hop, AS path and local-pref by design and just adds ORIGINATOR_ID and CLUSTER_LIST. Before I'm done I'd also rule out an inbound filter on the iBGP peer and a lower-AD source like OSPF at 110 beating iBGP at 200.
