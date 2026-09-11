---
id: pe-sd-01
domain: pe
topic: system_design
difficulty: hard
tags: [rate-limiting, caching, failure-modes]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a distributed rate limiter for an API gateway handling 1M requests per second.

## What interviewers look for
- Nails down requirements first: what's the limit unit (per API key, per IP, per tenant+endpoint), the window, and whether over-limiting or under-limiting is worse
- Does the arithmetic aloud — 1M QPS against a counter store, fan-out per request, why a naive single-Redis design won't hold
- Picks a explicit point on the accuracy-vs-latency curve and defends it rather than claiming perfect global accuracy
- Treats the limiter as a dependency that will fail and designs the degradation path before being asked
- Talks about hot tenants and fairness, not just aggregate throughput

## Strong answer covers
1. Algorithm choice with trade-offs: fixed window (cheap, boundary bursts of 2x), sliding window log (accurate, O(requests) memory), sliding window counter, token bucket / leaky bucket (allows configured burst, smooth refill) — recommends token bucket for API quotas and says why
2. Scale estimate: 1M QPS means every request does at least one limiter decision; a Redis instance does ~100k ops/s so a central counter needs ≥10-20 shards even before replication or headroom, and a same-DC RTT of ~0.5ms plus queueing is a real tax on a p99 budget
3. State placement options compared: (a) central Redis/memcache cluster with an atomic Lua script or INCR+EXPIRE, sharded by key; (b) local per-gateway buckets with quota divided by node count; (c) hybrid — local buckets that periodically sync/borrow from a central authority every ~100ms-1s. Notes local-only drifts when traffic is skewed across gateways and when nodes autoscale
4. Hot keys: a single large tenant's key lands on one shard; mitigations include key splitting into N sub-buckets with client-side random selection, per-key local caching of 'already over limit' decisions, and dedicated shards for whale tenants
5. Failure behaviour made explicit: limiter backend down or slow → short timeout (single-digit ms), fail-open for most traffic to protect availability, but fail-closed for abuse-sensitive or expensive endpoints; local fallback buckets as a floor; never block on the limiter with unbounded waits
6. Fairness and multi-tier limits: per-tenant quotas plus a global capacity limit / load shedder so one tenant can't consume the fleet, priority classes, and rejecting with HTTP 429 plus Retry-After and X-RateLimit-* headers
7. Observability: allowed vs throttled rate per tenant and per rule, limiter decision latency p99, backend error rate and timeout rate, fail-open events as a first-class metric with an alert, and a dry-run/shadow mode when introducing a new rule
8. Operational concerns: rules as versioned config with staged rollout, ability to raise a tenant's limit without a deploy, and clock/window alignment so all nodes agree on bucket boundaries

## Follow-ups
- A customer complains they're being throttled at 700 rps against a 1000 rps limit. How do you debug, and what in your design could produce that under-allowance?
- Now the limit must be enforced globally across three regions with 80ms of RTT between them. What changes, and what accuracy do you promise?
- You need to add a cost-based limit — some requests count as 50 units — while keeping the same latency budget. How?
- The limiter cluster loses a third of its shards. Walk me through what users see minute by minute and what recovery looks like.

## Sample answer
First, what's the unit and what failure is worse? I'll assume per-API-key limits on a gateway fleet, and that briefly allowing extra traffic is better than rejecting good traffic. I'd use a token bucket: it gives a configured burst and a smooth refill rate, and it's one counter plus a timestamp per key. At 1M QPS every request needs a decision. A Redis node does maybe 100k ops/s, so a central store is 10-20 shards minimum plus headroom — and it adds a round trip to every request. So I'd go hybrid: each gateway keeps local buckets and leases quota from a sharded central authority every couple hundred milliseconds. Decisions are local and sub-microsecond; the central tier only handles reconciliation, so it's not on the hot path. The trade-off is accuracy — I'd promise roughly right, not exact, with over-allowance bounded by the lease size. Hot tenants get key-splitting across sub-buckets. If the central tier is unavailable, gateways keep enforcing their last lease and fail open after a short timeout, except on expensive endpoints where I'd fail closed; fail-open events are a metric I alert on. I'd expose allowed/throttled per tenant, decision latency, and run new rules in shadow mode before enforcing.
