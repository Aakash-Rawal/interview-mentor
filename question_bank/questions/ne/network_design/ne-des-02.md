---
id: ne-des-02
domain: ne
topic: network_design
difficulty: medium
tags: [cloud, multi-region, rpo-rto, vpc]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a multi-region VPC architecture for a service that must survive a full region outage.

## What interviewers look for
- Asks for RPO/RTO targets and the data tier's replication capability before picking active-active vs active-passive
- Treats non-overlapping CIDR planning as a first-class decision, including future regions and on-prem/partner space
- Distinguishes the failover mechanism (DNS TTL vs anycast/global LB health checks) and states realistic failover times
- Names what actually breaks in a region failover — stateful data, quotas/capacity in the surviving region, control-plane dependencies
- Insists the failover is tested on a schedule, not assumed

## Strong answer covers
1. Requirements: RPO and RTO as explicit numbers, whether writes can be served from two regions, latency budget, compliance/data-residency, cost ceiling
2. Per-region VPC with non-overlapping CIDRs allocated from a planned supernet (e.g. /16 per region, /20 per AZ-subnet tier), reserving space for future regions and avoiding overlap with on-prem and partner RFC1918 space
3. Multi-AZ subnet layout inside each region (≥3 AZs, separate public/private/data subnet tiers per AZ) so an AZ loss is handled locally before region failover is needed
4. Inter-region connectivity: transit gateway peering or VPC peering hub, with a hub-and-spoke transit design rather than full mesh; private replication path rather than public internet
5. On-prem connectivity: redundant Direct Connect/Interconnect circuits terminating in separate facilities, into at least two regions, with BGP and route filtering; VPN as diverse backup
6. Failover mechanism: global load balancer or anycast for active-active with RPO≈0; DNS failover with health checks and short TTLs for active-passive (RTO in minutes, clients that cache TTLs will lag); state the data conflict problem for active-active writes
7. Supporting design: egress via NAT gateways per AZ with cost awareness, private DNS zones / split-horizon resolution per region, security groups as microsegmentation, replicated secrets and container images
8. Testing and readiness: scheduled region-evacuation game days, capacity reserved in the passive region (not just autoscaling hope), runbook plus dependency audit for control-plane calls into the failed region

## Follow-ups
- Your database only supports single-writer. How does that change the design, and what is your honest RPO during an unplanned region loss?
- The region isn't down — it's degraded, 20% error rate. How does your health-check and failover logic avoid flapping?
- Walk me through the cost of this design and where you'd cut first if the budget were halved.
- How do you keep the two regions' configuration identical, and how would you detect drift before it bites you during a failover?

## Sample answer
I start with RPO and RTO, because that decides active-active versus active-passive. If the data tier is single-writer, be honest: it's active-passive with an RTO of minutes and an RPO of whatever the replication lag is. Addressing: one planned supernet, a /16 per region carved into per-AZ subnet tiers, non-overlapping with each other, with on-prem, and with partner space — and I reserve space for regions we haven't built yet. Three AZs per region so an AZ loss never triggers a region failover. Between regions I use transit gateway peering in a hub-and-spoke rather than a peering mesh, and replication rides that private path, not the internet. On-prem gets two Direct Connect circuits in different facilities, landing in two regions, with VPN as diverse backup. Failover is a global load balancer with health checks if the app is stateless — effectively anycast, RPO zero; otherwise DNS failover with short TTLs, accepting that some clients cache longer. Details that bite people: NAT gateway egress cost, split-horizon private DNS per region, replicated images and secrets, and reserved capacity in the passive region rather than trusting autoscaling. And I schedule a real region evacuation quarterly, because untested failover is just documentation.
