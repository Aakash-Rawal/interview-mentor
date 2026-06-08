# Network Design (Network Engineering)

## Datacenter fabric: spine-leaf (Clos)
- Every leaf connects to every spine; no leaf-to-leaf or spine-to-spine.
- Predictable latency (always 2 hops east-west), horizontal scale by adding spines.
- Typically L3 to the leaf with BGP (or eBGP per ToR), ECMP across spines.
- Oversubscription ratio (e.g. 3:1) is the key capacity-planning number.

## Load balancing
- **L4 (transport)**: balances by IP/port, fast, no payload awareness (e.g. IPVS, NLB).
- **L7 (application)**: HTTP-aware routing, TLS termination, path/header rules (e.g. Envoy, NGINX, ALB).
- Algorithms: round-robin, least-connections, consistent hashing (sticky, cache-friendly).
- Health checks + connection draining for safe rollouts.

## CDN / edge
- Push content close to users; cache static, route dynamic to origin.
- Anycast IPs route users to the nearest PoP via BGP.
- Key knobs: TTLs, cache keys, origin shielding, purge strategy.

## Cloud VPC design
- VPC = isolated L3 space; subnets per AZ (public vs private).
- Public subnet → internet gateway; private → NAT gateway for egress only.
- Peering / transit gateway to interconnect VPCs; watch for overlapping CIDRs.
- Security groups (stateful, instance-level) vs NACLs (stateless, subnet-level).

## High availability
- Multi-AZ for fault tolerance; multi-region for disaster recovery.
- Redundant links + ECMP; graceful failover (BFD for sub-second detection).
- No single point of failure: dual ToRs, dual uplinks, dual power.

## Capacity planning
- Estimate peak bandwidth, packet rate, concurrent flows. Size for peak + headroom.
- Watch buffer/queue depth for microbursts; throughput ≠ packet-per-second limit.

## Interview behaviour
Start with requirements: scale (servers, bandwidth, regions), failure domains,
latency budget. State assumptions, then defend against failure modes.
