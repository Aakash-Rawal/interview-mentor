---
id: pe-sd-06
domain: pe
topic: system_design
difficulty: medium
tags: [caching, invalidation, stampede]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design the caching layer for a read-heavy product catalogue service with 100:1 read/write ratio and strict freshness on price changes.

## What interviewers look for
- Pins down what 'strict freshness on price changes' actually means in seconds and what the business cost of a stale price is
- Picks invalidation strategy deliberately and names its failure mode (lost invalidation, ordering, races)
- Brings up stampede/dogpile unprompted with concrete mitigations
- Reasons about the cache being a capacity dependency, not an optimisation — i.e. can the origin survive a cold cache?
- Quantifies hit rate, origin QPS, and working-set size rather than hand-waving

## Strong answer covers
1. Requirements clarification: freshness budget for prices (is 1s, 5s, or 60s acceptable?), whether stale-but-fast is acceptable for descriptions/images while price must be fresh, read QPS and catalogue size, and legal/commercial consequences of serving a wrong price (often 'must never show a price we won't honour' → serve price separately or validate at checkout)
2. Estimate: with 100:1 read/write and, say, 50k read QPS, a 95% hit rate leaves 2,500 QPS to the origin; a 90% hit rate leaves 5,000 — so the hit-rate assumption directly sizes the database, and the working set (items × bytes) determines whether it fits in RAM
3. Strategy comparison: cache-aside (simple, origin is source of truth, has a miss-storm and race window), write-through (cache always populated, write latency includes cache, still needs a fallback), write-behind (fast writes, durability risk), and read-through via a caching layer; recommends cache-aside with explicit invalidation plus a short TTL as a safety net
4. Freshness mechanism: on a price update, publish an invalidation/update event (via the DB change stream or a pub/sub fanout) to all cache nodes and edge caches; use a short TTL (seconds) as backstop for lost invalidations; version or monotonic-timestamp the cached value so a slow origin read can't overwrite a newer value (compare-and-set or write-if-newer); consider splitting the entity so volatile price lives in a small, short-TTL entry and stable product data has a long TTL
5. Stampede protection: per-key mutex/lease so only one request repopulates a key while others wait or serve stale, request coalescing/single-flight in the service, probabilistic early expiration (refresh before TTL with jitter), negative caching for missing items, and never a fleet-wide synchronised TTL — jitter TTLs to avoid correlated expiry
6. Hot keys: a front-page item can concentrate traffic on one shard; mitigate with a small in-process L1 cache with a 1-second TTL on every app node, key replication across shards, or client-side load spreading. Note the L1 widens the consistency window and must also be invalidated (or kept to sub-second TTL)
7. Cache failure behaviour: cluster loss means 100% miss and 20x origin load — so the origin needs either enough headroom, an admission/load-shedding path, or a request limiter that serves stale/degraded responses; discuss cold-start warming, gradual traffic admission, and consistent hashing so losing one node reshuffles only 1/N of keys rather than everything
8. Consistency window statement: explicitly say 'prices are eventually consistent within X seconds, bounded by invalidation fanout latency plus L1 TTL', and cover the correctness fallback — re-validate price at add-to-cart/checkout against the source of truth
9. Observability: hit ratio overall and per key class, origin QPS and p99, invalidation lag (publish → applied on all nodes), stale-serve count, eviction rate and memory pressure, hot-key detector, and an alert on hit-rate drop as a leading indicator of origin overload

## Follow-ups
- An invalidation message is lost for one cache node. How long does a wrong price persist, how would you detect it, and how do you bound the damage?
- The cache cluster is lost entirely during peak traffic. Talk me through the first ten minutes and how you bring it back without a retry storm.
- Marketing wants a flash sale: one SKU gets 200k QPS for ten minutes. What changes?
- Would you push invalidation or have caches poll a change feed? Argue both sides at 1,000 cache nodes.

## Sample answer
I'd first make 'strict freshness' a number — is a five-second-old price acceptable? Usually the real requirement is 'never charge a price we didn't show', which I'd satisfy by re-validating price at checkout against the database, so the cache only needs to be approximately fresh. Then I'd split the entity: stable product data gets a long TTL, volatile price gets its own small entry with a few-seconds TTL. Design is cache-aside with explicit invalidation: price writes emit an event from the DB change stream, fanned out to all cache nodes, with the short TTL as a backstop for lost invalidations, and version numbers on cached values so a slow origin read can't clobber a newer write. Sizing matters: at 50k read QPS, 95% hit rate means 2,500 QPS to the origin, 90% means 5,000 — so the hit rate is a capacity decision, and I'd alert on hit-rate drops as a leading indicator. For stampedes: single-flight per key, serve-stale-while-revalidating, probabilistic early refresh, and jittered TTLs so nothing expires in lockstep. Hot keys get a 1-second in-process L1 cache, accepting a slightly wider staleness window. If the cluster dies, I get 20x origin load, so the origin needs a load shedder and I'd re-admit traffic gradually while the cache warms. Consistent hashing keeps a single node loss to 1/N of keys.
