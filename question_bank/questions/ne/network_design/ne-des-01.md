---
id: ne-des-01
domain: ne
topic: network_design
difficulty: hard
tags: [clos, bgp, oversubscription, datacenter]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a datacenter network for 10,000 servers. Walk me through topology, routing, oversubscription, and how you'd handle a spine failure.

## What interviewers look for
- Gathers requirements before drawing: east-west vs north-south ratio, bandwidth per server, VM-mobility/L2 needs, availability target, growth rate
- Does the port arithmetic out loud — leaf port counts, uplink bandwidth, rack count, pod count — rather than saying 'spine-leaf' and stopping
- Justifies the oversubscription ratio from the traffic profile instead of quoting a default
- Walks the spine failure quantitatively (capacity −1/N, not an outage) and mentions N−1/N−2 sizing
- Volunteers operational concerns unprompted: OOB, automation, staged rollout, telemetry

## Strong answer covers
1. Requirements first: servers and growth, east-west vs north-south mix, per-server bandwidth (e.g. 25G), latency, availability target, multi-tenancy, L2/VM-mobility need, budget and automation/vendor constraints
2. Folded 3-stage Clos (spine-leaf), extended to 3-tier with super-spines and pods when one spine plane is exhausted; spines never interconnect; pod = unit of growth
3. Port arithmetic: e.g. 48 × 25G server ports + 8 × 100G uplinks per leaf = 1200G down / 800G up = 1.5:1; a 3:1 ratio is common for general compute, 1:1 for storage/ML fabrics
4. Scale arithmetic: 10,000 servers ≈ 210 racks at 48 servers/rack → e.g. 4 pods × 64 leaves, 4–8 spines per pod, super-spines tying pods together; spine radix bounds pod size
5. L3 to the leaf with eBGP per RFC 7938: unique ASN per leaf (or per pod with iBGP inside), /31 or unnumbered p2p links, loopback /32s advertised, ECMP across all uplinks, BFD for sub-second detection, allowas-in / ASN reuse caveats
6. Why eBGP over OSPF: policy control, smaller blast radius, no fabric-wide LSA flooding, vendor neutrality, easier troubleshooting per-hop
7. L2 requirements handled by EVPN-VXLAN overlay with anycast gateway, keeping the underlay pure L3; per-rack /26–/24 for servers or routed-to-host
8. Spine failure: with 4 spines, losing one is 25% capacity loss absorbed by ECMP — no outage; size spines N+1 for peak, target upgrade at 60–70% p95 utilisation, model N−1 and N−2
9. Operations: separate OOB management network with console servers, IPAM/source-of-truth driven config generation, staged per-pod rollouts, streaming telemetry on interface/ECMP state

## Follow-ups
- Servers are dual-homed. Would you use MLAG/ESI-LAG to a leaf pair, or single-homed with the rack as the failure domain? Argue the cost and complexity both ways.
- A leaf's uplink to one spine goes to 100% while the other seven sit at 30%. What causes that with ECMP, and how do you fix it?
- How do you upgrade spine software on a live fabric without dropping traffic, and how do you drain a spine from the fabric in BGP?
- Your east-west traffic doubles in a year. Walk me through the upgrade path — does the ratio, the optics, or the port speed generation change first?

## Sample answer
First, requirements: 10,000 servers at 25G each, mostly east-west, so I care about the leaf oversubscription ratio more than the edge. Growth to maybe 15,000; do they need L2 adjacency for VM mobility, and what's the availability target? Topology is a folded Clos. A leaf with 48 × 25G down and 8 × 100G up is 1200G down against 800G up — 1.5:1. If the profile is more north-south-ish I'd take 3:1 and save optics; for storage or ML I'd go 1:1. 10,000 servers at 48 per rack is about 210 leaves, so I'd build four pods of 64 leaves with eight spines each and super-spines between pods — pod is my unit of growth and my blast radius. Routing is L3 to the leaf, eBGP per RFC 7938, ASN per leaf, /31 or unnumbered p2p links, loopbacks advertised, ECMP eight ways, BFD for fast detection. If they need L2 I put EVPN-VXLAN on top with an anycast gateway and keep the underlay pure IP. Spine failure: losing one of eight is 12.5% capacity, ECMP reconverges in under a second with BFD, no outage. I size for N−1 at peak and upgrade links at 60–70% p95. And a real out-of-band network with console servers, because otherwise you can't recover from your own change.
