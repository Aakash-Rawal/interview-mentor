---
id: pe-sd-07
domain: pe
topic: system_design
difficulty: hard
tags: [multi-region, failover, replication, rto-rpo]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Your service runs in one region. Design the path to surviving a full region outage with under 5 minutes of downtime and minimal data loss.

## What interviewers look for
- Defines RTO and RPO as numbers first, then lets those numbers drive the replication and steering choices rather than picking a topology up front
- Budgets the 5 minutes explicitly across detection, decision, traffic steering, and warm-up instead of treating failover as instantaneous
- Treats the failover mechanism itself as a system that can fail — control-plane placement, split brain, fencing, automated vs human-triggered
- Enumerates the boring dependencies that block a real evacuation (secrets, certs, artifacts, service discovery, capacity, cold caches)
- Insists on regularly exercising failover and failback in production, with measured results, not a documented-but-untested procedure

## Strong answer covers
1. States a target pair: RTO < 5 min and an explicit RPO (e.g. RPO 0 vs RPO ≈ 10 s of writes), and notes they are separate dials
2. Budgets the RTO: health-check detection ~30-60 s, decision/automation ~30 s, DNS/anycast convergence 60-120 s, connection re-establish and cache warm 60+ s — shows 5 min is tight
3. Replication trade-off with numbers: synchronous cross-region adds one 50-150 ms RTT to every commit (RPO 0, latency and availability coupling); async gives fast local writes but RPO equals replication lag, which must be monitored and alerted on; mentions quorum across 3 regions as a middle option
4. Active-passive (warm standby, cheaper, but unexercised path and cold caches) vs active-active (already serving, proven, but needs conflict resolution / partitioned write ownership and per-region data locality); picks one and justifies it against the 5 min RTO
5. Traffic steering options compared: DNS with low TTL (clients and resolvers ignore TTLs, minutes of tail), GSLB/health-checked DNS, anycast + BGP withdrawal (seconds but coarse), client-side retry/failover; health checks run from multiple external vantage points, not from inside the failing region
6. Failover control plane lives outside both regions (or is quorum-based across three failure domains); discusses split brain when the 'outage' is a network partition — fencing tokens, leases, a single authoritative promoter, and why a human-confirmed big-red-button is often chosen over full automation
7. Dependency audit for the standby: pre-provisioned capacity for 100% of traffic (not autoscaling from zero), secrets and certificates present, container images/artifacts replicated, service discovery and config, DB schema at the same version, no hidden calls back into the dead region
8. Recovery hazards: cold cache causing a database overload spike, connection/retry storms, backlog drain on queues; plus a written failback procedure (re-replicate, catch up, verify, then move traffic back)
9. Regular testing: scheduled region evacuation game days measuring actual RTO/RPO, plus cost framing (roughly 2x footprint for a hot standby, cross-region replication egress often the dominant bill line)

## Follow-ups
- The failover completes but the async replica was 40 seconds behind — some acknowledged writes are gone. How do you detect which ones, and what do you tell the users and downstream systems?
- How do you handle the grey failure case: the region isn't down, it's 20% error rate and rising. What triggers evacuation, and who or what decides?
- Stateful middleware — Kafka, ZooKeeper/etcd, an in-region job scheduler — doesn't fail over like a stateless service. Walk me through one of them.
- Design the failback: the dead region comes back an hour later. What's the sequence, and what's the most likely way it hurts you?

## Sample answer
First I'd nail the two numbers. RTO under 5 minutes is given; RPO I'd push on, because it decides everything. If the business can tolerate a few seconds of lost writes, async replication is fine and my writes stay at single-digit milliseconds. If RPO must be zero, every commit pays a cross-region round trip — 50 to 150 ms — and my primary region's availability now depends on the other region, which is a real cost. I'd usually land on async with a monitored, alerted replication-lag SLI, or a three-region quorum if RPO 0 is genuinely required. Then I'd budget the five minutes: detection 30-60 s from external health checks, decision 30 s, traffic steering 60-120 s, then cache warm and connection re-establishment. DNS TTLs lie, so I'd prefer anycast withdrawal or a GSLB in front. Standby capacity is pre-provisioned for full load, not autoscaled. The failover controller lives in neither region and uses leases and fencing tokens so a partition doesn't give me two primaries — I'd likely keep a human on the trigger and automate everything after it. Then the unglamorous part: secrets, certs, images, schema version, and no hidden calls back into the dead region. And I'd evacuate the region on a schedule and publish the measured RTO, because an untested failover is a hypothesis.
