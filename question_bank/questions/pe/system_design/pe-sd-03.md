---
id: pe-sd-03
domain: pe
topic: system_design
difficulty: medium
tags: [logging, storage-tiering, cost]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a centralised logging system for 50,000 hosts. Engineers need to search logs from the last 30 days within seconds.

## What interviewers look for
- Estimates bytes/host/day and turns it into storage cost and hardware before designing
- Distinguishes 'search recent logs fast' from 'keep everything 30 days cheaply' and tiers accordingly
- Identifies indexing as the expensive part and proposes controls (sampling, structured fields, selective indexing)
- States clearly what degrades first under load and why that's the right thing to sacrifice
- Mentions access control and PII, not just throughput

## Strong answer covers
1. Cost estimate: assume ~1 GB/host/day (say it's an assumption and ask); 50k hosts × 1 GB = 50 TB/day raw, ×30 days = 1.5 PB; at ~10:1 compression ~150 TB, plus an inverted index that can be 20-100% of data size again — so the index, not the raw bytes, drives cost. Average ingest ≈ 50 TB/86,400 s ≈ 600 MB/s, peak 3-5x
2. Pipeline shape: host agent (tail files/journald, add host/service/env metadata, bounded local buffer with backpressure to avoid filling the host's disk) → durable log like Kafka partitioned by service or host → indexers → hot/warm/cold storage; the queue decouples indexer outages from log producers
3. Storage tiering: hot on local SSD for last 24-48h with a full inverted index for sub-second search; warm on network storage with a lighter index for days 3-7; cold in object storage as compressed columnar or raw with only coarse metadata, searched by brute-force scan jobs with minute-scale latency. Be honest that 'seconds' applies to the hot/warm window and state what the cold experience is
4. Index design and cost control: structured JSON logging so fields are typed; index a whitelist of fields (service, host, level, trace/request ID, status) and leave the message body to full-text or grep-on-read; time-based indices to make deletion cheap (drop an index, don't delete documents)
5. Noisy source control: per-service ingest quotas, sampling of high-volume repetitive lines (e.g. keep 1 in 100 of a debug line but always keep errors), dedup/aggregate identical lines with counts, and a top-talkers dashboard so teams can see and own their volume
6. Load and degradation order: under overload, drop/sample low-severity logs first, let query latency degrade before ingest, shed expensive unbounded queries (no time range, wildcard leading terms), apply per-user query concurrency and cost limits; agents buffer then drop-oldest rather than blocking the application
7. Correlation and usability: structured logs with request/trace IDs so a search can pivot to a trace; consistent timestamp handling and a clock-skew guard; retention exceptions for audit logs
8. Access control and compliance: per-service/per-team read ACLs, redaction or blocking of secrets and PII at the agent, audit trail of who searched what, and a deletion path for regulated data
9. Failure modes: Kafka partition loss, indexer falling behind (alert on consumer lag and end-to-end log latency), hot node loss with replication factor choices, and recovery behaviour when 50k agents reconnect at once (jittered reconnect, rate-limited catch-up)

## Follow-ups
- During a major incident, log volume from one service goes up 100x — exactly when engineers most need search. How does your design behave, and is that the right behaviour?
- The bill is twice the budget. Give me three levers ranked by savings-to-pain ratio.
- An engineer needs to find one request ID across the full 30 days. How does that query execute and how long does it take?
- Would you build this or buy a managed service? Make the argument with numbers and name what you'd still have to build yourself.

## Sample answer
Assume roughly a gigabyte of logs per host per day — I'd check that. 50k hosts is 50 TB/day, 1.5 PB over 30 days raw, maybe 150 TB compressed, and the inverted index can add nearly as much again. That's about 600 MB/s average, several gigabytes a second at peak. So the design is: agents tail and enrich with host/service metadata, buffer locally with a bounded disk queue, ship into Kafka partitioned by service. Indexers consume and write time-based indices: hot on SSD for 48 hours fully indexed for sub-second search, warm for a week with a lighter index, then cold in object storage where search is a scan job taking minutes. I'd be explicit that 'seconds' means the last few days; I'd sell that trade-off rather than pretend. Cost control is mostly index control: structured logs, index only a field whitelist plus request IDs, full-text on the body only in hot tier, and per-service ingest quotas with sampling of repetitive debug lines while always keeping errors. Under overload I degrade in a fixed order: sample low-severity logs, reject unbounded queries, let query latency slip — never block the application's writes. SLIs: end-to-end log latency p99, consumer lag, query p95 by tier, drop rate by reason. Plus per-team ACLs and agent-side redaction.
