# Network Design — Network Engineering

## What this interview actually tests
Whether you can turn requirements into a topology with numbers — ports, oversubscription,
address plan, routing, failure domains — and defend the trade-offs. Scored on requirements
gathering, topology choice, routing design, failure-mode analysis, capacity planning, and
trade-off articulation. Say the assumptions; do the arithmetic aloud.

## The shape of a design answer
1. **Requirements** — server count and growth, east-west vs north-south ratio, bandwidth per
   server, latency, availability target, L2 needs (VM mobility?), multi-tenancy, budget,
   operational constraints (automation, vendor).
2. **Topology** — pick it and say why; draw tiers; count ports.
3. **Addressing & L2/L3 boundary** — where routing starts; VLAN/VXLAN scope; IP plan.
4. **Routing & control plane** — protocol, ASN scheme, ECMP, BFD, policy.
5. **Failure modes** — walk one failure per tier: what's the capacity after it?
6. **Capacity & growth** — oversubscription ratio, headroom, how you add a pod.
7. **Operations** — automation, OOB management, telemetry, change safety.

## Data-center fabric (Clos / spine-leaf)
- **Leaf (ToR)**: e.g., 48 × 25G server ports + 8 × 100G uplinks → 1200G down / 800G up =
  **1.5:1 oversubscription**. Choose the ratio from the east-west profile; 3:1 is common,
  1:1 for storage/ML fabrics.
- **Spine**: every leaf connects to every spine; spines never connect to each other. Spine
  count × spine port count bounds the pod size. Losing one of 4 spines = 25% capacity loss,
  not an outage, thanks to ECMP.
- **Super-spine / pods**: 3-tier Clos to scale beyond one spine plane; pod = unit of growth.
- **L3 to the leaf** with **eBGP** (ASN per leaf or per pod, RFC 7938), /31 or unnumbered
  point-to-point links, ECMP, BFD; loopbacks advertised; servers on /26–/24 per rack or
  routed to the host. Why not OSPF: policy, blast radius, vendor neutrality, scale of
  LSA flooding.
- **L2 needs** (VM mobility, legacy) → EVPN-VXLAN overlay with anycast gateway; keeps the
  underlay pure L3.
- 10,000 servers ≈ 210 racks at 48/rack → e.g., 4 pods × 64 leaves; 4–8 spines per pod;
  super-spines connecting pods. Do this arithmetic in the interview.

## Addressing plan (10/8 for 20 DCs, 10 years)
Hierarchical for **summarisation**: per DC /12–/14, per pod /16, per rack /24–/26, separate
ranges for loopbacks (/32s), point-to-point (/31s from one block), management/OOB, and
services/VIPs. Reserve 50% for growth. Avoid overlap with partners/cloud VPCs. IPAM as the
source of truth. Mistakes: sizing to today, no summarisation, VLAN-per-everything.

## Cloud / multi-region
- Per-region VPC with non-overlapping CIDRs; multi-AZ subnets; transit gateway / peering hub;
  private connectivity (Direct Connect/Interconnect) for on-prem, with redundant circuits in
  separate facilities.
- Region outage survival: active-passive (DNS/global LB failover, replicated data, RTO
  minutes) vs active-active (anycast/global LB, data conflicts, RPO ~0 but complex). Say RPO/RTO.
- Egress design (NAT gateways, cost), DNS (private zones, split-horizon), security groups as
  microsegmentation.

## Internet edge / peering
- Two edge routers per site, eBGP to ≥2 transit providers, IXP peering for cheap direct paths.
- **Outbound** control: LOCAL_PREF (peer > transit), communities. **Inbound**: prepend,
  more-specifics, provider communities; accept that it's approximate.
- Protections: max-prefix, prefix-lists both directions, RPKI ROV, bogon filtering, BFD,
  GTSM (TTL security), CoPP for control plane.
- Failure: one site loses all transit → iBGP between sites + enough backhaul; DDoS →
  scrubbing/RTBH/flowspec.

## Campus (500 people)
VLANs per function (users, voice, printers, guest, IoT, mgmt), SVIs on a redundant core
(stack/MLAG/VRRP), 802.1X + dynamic VLAN, guest isolated with internet-only, DHCP/DNS
placement, redundant uplinks with LACP, Wi-Fi controller design. A single core is a SPOF —
pair it or state the accepted risk.

## Failure-mode walk (do it per tier)
| Failure | Effect | Design answer |
|---|---|---|
| ToR dies | rack offline | dual-homed servers (MLAG/ESI) or accept rack as failure domain |
| Spine dies | capacity −1/N | ECMP; N+1 spines sized for peak |
| Link flaps | ECMP churn, microloops | BFD, dampening, LFA/fast reroute |
| Control-plane bug | fabric-wide | staged rollouts, per-pod blast radius, vendor diversity |
| OOB unreachable | can't recover | separate OOB network + console servers |
| DC loses transit | site isolated | inter-site backhaul + iBGP, DNS failover |

## Capacity planning
Measure p95 utilisation per link class, headroom target (e.g., upgrade at 60–70%), growth
forecast per pod, lead times for optics/circuits, model the N−1 (and N−2 for spines) case.
Cost levers: oversubscription ratio, optics (SR vs LR), port speed generations.

## Common mistakes
- Not counting ports or computing oversubscription; hand-waving "spine-leaf".
- L2 stretched everywhere (STP blast radius) when a routed fabric would do.
- No failure walk; no growth path; no OOB.
- Address plan without summarisation or growth reserve.
- Ignoring operations: automation, telemetry, change safety.

## Practice prompts
- 10,000-server fabric with topology, routing, oversubscription, and a spine failure.
- Multi-region VPC surviving a region loss; state RPO/RTO.
- Internet edge with 2 DCs and 3 transits; inbound TE and failure modes.
- Carve 10/8 for 20 DCs over 10 years. / 500-person office with a dead core.
