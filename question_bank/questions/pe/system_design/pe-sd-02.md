---
id: pe-sd-02
domain: pe
topic: system_design
difficulty: hard
tags: [metrics, cardinality, backpressure]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a metrics pipeline that ingests 10 million datapoints per second from a fleet and serves dashboards and alerts.

## What interviewers look for
- Separates the three distinct paths — ingest, query, alert evaluation — and explains why they must not share fate
- Quantifies: bytes per datapoint, storage per day and per year, series count, and derives host counts from that
- Raises cardinality as the number-one operational risk and proposes concrete controls
- Designs backpressure end-to-end instead of assuming infinite buffering
- Describes graceful degradation: what a dashboard and an alert each do when ingest is behind

## Strong answer covers
1. Capacity arithmetic: 10M datapoints/s; at ~16-24 bytes/point compressed (Gorilla-style delta-of-delta + XOR) that's roughly 200 MB/s or ~15-20 TB/day raw before downsampling, versus ~10x that uncompressed — so compression and retention tiers are load-bearing, not optional
2. Agent design: local aggregation/pre-aggregation on host, bounded in-memory or on-disk buffer with a drop policy, batching and compression, jittered send intervals to avoid fleet-wide synchronised spikes, and push vs pull trade-off (pull/scrape gives natural up-detection and flow control; push works better across NAT and for short-lived jobs)
3. Sharded ingestion tier: hash by series/metric name so a series always lands on the same shard, front it with a durable log (Kafka) so the storage tier can be restarted or fall behind without data loss, sized in partitions from the MB/s figure (tens of MB/s per partition)
4. Storage: TSDB with time-partitioned blocks, hot in-memory/SSD for recent data, downsampled rollups (e.g. raw 15s for 2 days, 1m for 30 days, 5m/1h for 13 months) on cheaper storage; queries pick the coarsest resolution that satisfies the range
5. Cardinality control: per-tenant/per-metric series budgets, rejecting or truncating high-cardinality labels (request IDs, user IDs, full URLs), a 'top offenders by new-series rate' report, and an emergency block-list — because one bad label multiplies series count and blows up memory in the index, not just disk
6. Alerting path independence: evaluate rules against the ingest stream or a dedicated read path so a slow ad-hoc dashboard query cannot starve alert evaluation; separate query quotas/pools; alert on staleness/no-data so a silent pipeline pages someone
7. Backpressure and overload: bounded queues at every hop, load shedding by priority (drop debug/low-value metrics before SLI metrics), sampling as last resort, and being explicit that data loss is preferable to unbounded memory growth
8. Failure modes: ingest outage → agents buffer for N minutes then drop oldest; Kafka lag → alerting freshness SLI degrades, so alert on evaluation delay; query tier overload → per-query timeouts, result limits, and circuit breakers; recovery → controlled backlog drain rate so replay doesn't re-overload storage
9. SLIs: ingest success rate, end-to-end freshness p99 (datapoint timestamp to queryable), alert evaluation delay, query latency p99 by range, and drop rate by reason

## Follow-ups
- A team ships a label containing a user ID and series count jumps 50x in ten minutes. What happens in your system, what pages, and what do you do in the first five minutes?
- How do you handle out-of-order and late-arriving points from agents that buffered through a 20-minute outage without corrupting rollups?
- Engineers want 1-second resolution for a handful of critical metrics. How do you support that without 15x-ing the whole pipeline?
- How would you make this multi-region so that a region losing its ingest tier still has working alerts for its own services?

## Sample answer
Let's size it. 10M points/s at roughly 20 bytes compressed is about 200 MB/s — order 15-20 TB a day. That means retention tiers and downsampling are core design, not an afterthought. Three paths that must not share fate: ingest, query, alert evaluation. Agents pre-aggregate on host, buffer to disk with a bounded queue and a drop-oldest policy, batch with jitter so 50k hosts don't all send on the same second. Ingest is sharded by series hash, fronted by Kafka so I can restart or lag the storage tier without losing data; at 200 MB/s that's a few dozen partitions with headroom. Storage is a TSDB with hot recent blocks on SSD and rollups — 15s for two days, 1m for a month, 5m beyond — chosen automatically by query range. The real risk is cardinality: one label with a user ID in it multiplies series and kills the index. So per-tenant series budgets, label validation, a new-series-rate report, and an emergency block-list. Alert evaluation gets its own read path and quota so a heavy dashboard query can't delay paging, and I alert on freshness and no-data so a silent pipeline is itself an alert. Under overload I shed low-value metrics first and drain backlogs at a rate limit so replay doesn't re-melt storage.
