# Routing Protocols (Network Engineering)

## BGP (the one to know cold for big-tech NE)
- Path-vector, runs over TCP/179. eBGP (between ASes) vs iBGP (within an AS).
- **Path selection order** (memorise): Weight (Cisco, local) → Local Preference →
  locally originated → shortest AS_PATH → lowest origin (IGP<EGP<incomplete) →
  lowest MED → eBGP over iBGP → lowest IGP metric to next-hop → oldest →
  lowest router-ID → lowest neighbour address.
- **Timers**: keepalive 60s, hold 180s default. Hold expiry tears the session.
- **States**: Idle → Connect → Active → OpenSent → OpenConfirm → Established.
- Common failures: flapping (route dampening), wrong next-hop on iBGP
  (`next-hop-self`), AS_PATH loops, missing route advertisement.

## OSPF
- Link-state IGP, areas around a backbone (area 0). Uses Dijkstra/SPF.
- **LSA types**: 1 Router, 2 Network, 3 Summary, 4 ASBR-Summary, 5 External, 7 NSSA-External.
- DR/BDR elected on multi-access segments to limit adjacencies.
- Cost = reference-bandwidth / interface-bandwidth.

## EIGRP
- Cisco hybrid; DUAL algorithm, feasible successor = precomputed backup path.
- Fast convergence; metric from bandwidth + delay by default.

## Redistribution (where bugs live)
- Translating routes between protocols. Risks: routing loops, suboptimal paths,
  metric mismatch. Use route-maps/tags to control what leaks and prevent feedback.

## Static & default
- Static routes for stub/predictable paths; `0.0.0.0/0` default to upstream.
- Administrative distance picks the winner across protocols (lower = preferred):
  connected 0, static 1, eBGP 20, OSPF 110, iBGP 200.
