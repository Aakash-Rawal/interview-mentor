# Routing Protocols — Network Engineering

## What this interview actually tests
BGP depth, above all. Big-tech NE loops assume you can narrate **path selection**, session
lifecycle, and failure/convergence with timers and numbers, then reason about blast radius
and policy. OSPF/IS-IS as the IGP underneath. Scored on protocol knowledge, path-selection
reasoning, failure analysis, blast-radius awareness, root-cause precision, fix and prevention.

## BGP — know cold
- Path-vector over **TCP/179**; eBGP between ASes (TTL 1 by default), iBGP within (full mesh
  or route reflectors / confederations). iBGP does **not** change next-hop → `next-hop-self`
  or carry the link in the IGP; iBGP-learned routes aren't re-advertised to other iBGP peers.
- **Session states**: Idle → Connect → Active (means *trying*, not up) → OpenSent →
  OpenConfirm → Established. Stuck in Active/Connect = TCP can't complete (ACL, wrong IP,
  no route, TTL); OpenSent/Confirm = parameter mismatch (AS, router-id, capabilities).
- **Timers**: keepalive 60 s, hold 180 s default; negotiated to the lower. Hold expiry tears
  the session. **BFD** for sub-second detection (e.g., 300 ms × 3). Interface-down triggers
  immediate teardown when the peer is directly connected (fast external fallover).
- **Messages**: OPEN, UPDATE (NLRI + withdrawn + path attributes), KEEPALIVE, NOTIFICATION.
- **Attributes**: well-known mandatory ORIGIN, AS_PATH, NEXT_HOP; well-known discretionary
  LOCAL_PREF, ATOMIC_AGGREGATE; optional transitive AGGREGATOR, COMMUNITY; optional
  non-transitive MED.

### Path selection order (memorise; say it in order)
1. Highest **weight** (Cisco-local)
2. Highest **LOCAL_PREF** (iBGP-wide; outbound policy lever)
3. Locally originated (network/aggregate/redistribute)
4. Shortest **AS_PATH** (prepending = inbound lever)
5. Lowest **origin** (IGP < EGP < incomplete)
6. Lowest **MED** (compared only between same neighbouring AS by default)
7. **eBGP over iBGP**
8. Lowest IGP metric to next-hop
9. Oldest path (eBGP, stability) → lowest router-ID → lowest neighbour address
Multipath/ECMP relaxes the tie-break when paths are "equal" through step 8.

### Traffic engineering levers
| Direction | Lever |
|---|---|
| Outbound (which exit you use) | LOCAL_PREF, weight, filtering what you accept |
| Inbound (how others reach you) | AS_PATH prepend, more-specific announcements, MED (same AS only), communities the upstream honours (e.g., lower local-pref, no-export to peers) |
Inbound control is always weaker: the other side's local-pref beats your prepends.

### Failure walk-through: eBGP session drops (end to end)
Detection (hold 180 s default, BFD ~1 s, or immediate on link-down) → NOTIFICATION/teardown →
all routes from that peer removed from Adj-RIB-In → best-path re-run → withdrawals sent to
other peers; alternates promoted → RIB → FIB reprogrammed (hardware) → traffic shifts.
Downstream: withdrawal propagates AS by AS; route dampening may suppress a flapping prefix;
if no alternate, prefix disappears from the internet. Mention: graceful restart / LLGR keep
forwarding during a control-plane restart; blast radius = every prefix over that peer.

### Classic failure signatures
- Route in table but not installed on iBGP peer → next-hop unreachable.
- Traffic takes the longer AS path → LOCAL_PREF/weight set inbound by a route-map.
- Sudden transit between two upstreams → **route leak** (missing export filter). Prevent with
  default-deny export policy, communities tagging learned routes, max-prefix, RPKI/IRR.
- Flapping session → link errors, MTU (large UPDATEs), CPU, hold timer too aggressive.
- Prefix hijack → more-specific from the wrong origin; RPKI ROA + ROV, monitoring.
- MED confusion → only compared within the same neighbour AS unless `always-compare-med`.

## OSPF — know well
- Link-state IGP, areas around **area 0** backbone; SPF (Dijkstra) per area; ABR summarises,
  ASBR redistributes. Stub/NSSA reduce LSA flooding.
- **LSA types**: 1 router, 2 network, 3 summary, 4 ASBR-summary, 5 external, 7 NSSA external.
- **Neighbour states**: Down → Init (one-way hellos) → 2-Way → ExStart → Exchange → Loading →
  Full. Stuck **ExStart/Exchange = MTU mismatch** (or duplicate router-id). Stuck Init =
  one side not receiving hellos (ACL/auth/area/timer/network-type mismatch).
- DR/BDR on multi-access segments (priority, then router-id); point-to-point avoids election.
- Cost = reference bandwidth / interface bandwidth (default reference 100 Mbps — set it higher).
- Timers hello 10 / dead 40 (broadcast); BFD for fast detection.
- Convergence: detection → LSA flood → SPF → FIB. Tuning: LSA/SPF throttle timers, BFD, LFA.

## IS-IS (know the differences)
Runs directly over L2 (no IP dependency), levels 1/2, TLVs make it extensible (used in large
DC/backbone fabrics), NET addressing, DIS instead of DR, no backbone-area constraint.

## Redistribution (where bugs live)
Metric translation, routing loops when redistributing both ways, administrative distance
picking the wrong source, route tags to prevent feedback, always filter with prefix-lists.
AD defaults: connected 0, static 1, eBGP 20, OSPF 110, IS-IS 115, RIP 120, iBGP 200.

## Data-center routing patterns
eBGP to the leaf (unique ASN per leaf or per pod), ECMP across spines, /31 or unnumbered
links, BFD everywhere, communities for role/pod, EVPN-VXLAN for L2 overlay, anycast
gateways. Why BGP not OSPF in the DC: policy, scale, per-hop control, vendor-neutral.

## ECMP and hashing
Per-flow hash (5-tuple) keeps ordering; elephant flows can saturate one link while others
idle. Remedies: better entropy (UDP source port for VXLAN), flowlet switching, adaptive
routing, application-level multiple flows. Polarisation across tiers → vary hash seeds.

## Common mistakes
- Reciting path selection out of order or forgetting LOCAL_PREF beats AS_PATH.
- "Active means up." / Forgetting next-hop-self on iBGP.
- Hand-waving "blast radius" without saying which prefixes/peers/traffic are affected.
- No numbers: timers, prefix counts, detection time, convergence time.
- Applying a policy change without a filter test or a rollback plan.

## Practice prompts
- eBGP drop end to end with timers; then with BFD; then with graceful restart.
- Two paths, longer AS path chosen — find why. / iBGP route not installed.
- OSPF stuck in ExStart; stuck in Init. / Design inbound TE across three upstreams.
- Route leak after a prefix-list change: stop it, prevent it.
