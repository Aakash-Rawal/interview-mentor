---
id: ne-rt-06
domain: ne
topic: routing
difficulty: medium
tags: [ecmp, hashing, load-balancing, datacenter]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Explain how ECMP works and why a single elephant flow can still saturate one link even though four equal-cost links exist. What can you do about it?

## What interviewers look for
- Explains why per-flow hashing exists (ordering) before complaining about its downside
- Reasons about entropy — what fields the hash actually sees at each tier
- Offers layered remedies at network, overlay, and application levels with trade-offs
- Mentions polarisation across tiers and how to avoid it
- Talks about how you'd actually detect the imbalance in production

## Strong answer covers
1. Mechanism: the hash over the 5-tuple (src/dst IP, protocol, src/dst port) selects one member of the ECMP group; every packet of a flow hashes identically so it pins to one link — deliberate, to preserve packet ordering for TCP
2. Consequence: a single long-lived high-rate flow (backup, storage replication, model checkpoint sync) gets no benefit from N links — one 100G member can saturate while three sit near idle; ECMP balances flows, not bytes
3. Detection: per-member interface counters on the LAG/ECMP group, imbalance across members, drops/queue depth on one link only; sFlow/IPFIX or streaming telemetry to identify the top talker flow
4. Polarisation: identical hash functions and seeds at successive tiers cause all flows that took member 1 at the leaf to take member 1 at the spine — remedy is per-device hash seeds/offsets or including a device-unique salt
5. Entropy remedies for tunnels: VXLAN/GRE/MPLS hide the inner 5-tuple, so use a UDP source port derived from the inner flow hash (VXLAN), MPLS entropy labels, or ensure the transit devices do deep inspection of inner headers
6. Flowlet switching: split a flow at gaps larger than the maximum path-delay difference so reordering can't occur; used by adaptive-routing implementations
7. Adaptive/congestion-aware load balancing (per-packet spray with reordering handled at the NIC in RDMA/DCQCN environments, dynamic load balancing on member utilisation) — trade-off is reordering risk and hardware/NIC support
8. Application-level remedy: multiple parallel TCP connections or multipath TCP so the traffic presents as many flows; often the cheapest and most effective fix
9. Trade-off framing: per-flow = safe but coarse; per-packet = perfect balance but reordering kills TCP throughput unless the receiver tolerates it

## Follow-ups
- Your overlay is VXLAN and the spine can only hash on outer headers. Walk me through exactly how the entropy gets restored.
- You add a fifth link to a 4-way ECMP group. What happens to existing flows and why might that matter?
- How would you decide between telling the application team to open more connections versus buying adaptive routing hardware?
- In an RDMA/storage fabric you enable packet spraying. What has to be true about the endpoints for that to be safe?

## Sample answer
ECMP hashes the 5-tuple — source and destination IP, protocol, source and destination port — into a member index. Every packet of a flow hashes the same way, so the flow pins to one link. That's deliberate: it guarantees in-order delivery, and TCP hates reordering. But the unit of balancing is the flow, not the byte, so one elephant — a backup stream or a storage replication job — sees exactly one link's worth of capacity. Four 100G links and a 100G flow still congests one member while the other three idle. I'd detect it with per-member counters showing a lopsided distribution and drops on only one link, then IPFIX to name the flow. Remedies in order of cost. Check for polarisation first — if every tier uses the same hash function and seed, flows stack on the same member index all the way up, and per-device hash seeds fix that for free. If it's an overlay, make sure VXLAN is deriving the outer UDP source port from the inner flow hash, or use MPLS entropy labels, so the spine actually sees entropy. Then flowlet switching, which splits at inter-packet gaps larger than the path delay skew so reordering can't happen, or full adaptive routing. Cheapest of all is usually asking the application to open eight connections instead of one.
