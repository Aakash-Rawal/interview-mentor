---
id: ne-des-03
domain: ne
topic: network_design
difficulty: medium
tags: [addressing, ipam, summarisation, planning]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
You're given a 10.0.0.0/8 and asked to plan addressing for 20 datacenters over 10 years. How do you carve it up, and what mistakes do you avoid?

## What interviewers look for
- Designs top-down for summarisation rather than bottom-up from host counts
- Explicitly reserves growth at every level and says roughly how much (e.g. 50%)
- Separates functional ranges — loopbacks, p2p, management/OOB, services/VIPs — from server space
- Raises overlap risk with cloud VPCs, partners, and acquisitions, and IPv6/NAT as escape hatches
- Names IPAM as the source of truth and ties allocation to automation

## Strong answer covers
1. Do the arithmetic: 10.0.0.0/8 = 16 × /12 or 64 × /14; 20 DCs over 10 years means allocating for ~40 to leave headroom, so a /13 or /14 per DC with a reserved neighbour block for expansion
2. Hierarchical, aligned-on-bit-boundary allocation so every level summarises: /12–/14 per DC → /16 per pod → /24–/26 per rack or per-rack routed subnet
3. Separate dedicated blocks carved out once, globally: loopback /32s from one aggregate, point-to-point /31s from another, management/OOB, services/VIPs/anycast, lab/staging — each summarisable in BGP
4. Reserve roughly 50% for growth at every tier, and never allocate the next contiguous block to a different DC (keeps future expansion summarisable)
5. Overlap avoidance: don't collide with cloud VPC CIDRs, partner/VPN peers, acquisition space, or common defaults like 10.0.0.0/24 and 10.1.1.0/24; document which blocks are reserved-do-not-use
6. IPAM as the single source of truth, driving automation and config generation; allocation requests go through it, and reconciliation jobs detect drift and squatting
7. Mistakes to avoid: sizing to today's host counts, no summarisation so the fabric carries thousands of /24s, VLAN-per-everything, per-rack subnets so tight that one dense rack breaks the scheme, reusing loopback space for p2p
8. Mention IPv6 planned in parallel (e.g. a /48 or /44 per DC from a ULA or assigned prefix) and where NAT/translation is the last resort for an unavoidable overlap

## Follow-ups
- An acquisition arrives already using 10.0.0.0/8 overlapping yours. What are your options, ranked?
- How do you handle a rack that needs far more than a /26 — a subnet-per-rack scheme versus routing to the host?
- Two years in, somebody hand-allocated a /16 out of the middle of a reserved DC block. How do you find it and reclaim it?
- How would your plan change if you were designing IPv6-first with IPv4 only at the edge?

## Sample answer
I design top-down for summarisation, not bottom-up from host counts. 10/8 gives me 16 /12s or 64 /14s. Twenty DCs over ten years — I plan for forty, so a /14 per DC and I deliberately leave the adjacent /14 free so a DC can grow and still summarise as a single /13. Inside a DC, /16 per pod, then /24 or /26 per rack. Before any of that I carve global functional blocks: one aggregate for loopback /32s, one for point-to-point /31s, one for management and OOB, one for service VIPs and anycast, one for lab. That way each class summarises cleanly and I can write firewall and BGP policy against a single prefix. Rule of thumb: reserve half of everything at every level. The mistakes I'm avoiding are sizing to today, allocating non-contiguously so nothing summarises, and VLAN-per-everything. I also check overlap against our cloud VPC CIDRs, partner VPN peers, and the classic squatted ranges like 10.0.0.0/24 — and I keep a do-not-use list for acquisitions. Everything lives in IPAM as the source of truth, allocations go through it, and a reconciliation job flags anything in the network that IPAM doesn't know about. In parallel I'd plan IPv6 with a /48 per DC so I'm not retrofitting it later.
