# System Design — Production Engineering / SRE

## What this interview actually tests
Not app features — **operability at scale**. PE design questions are infrastructure-flavoured
(rate limiter, metrics pipeline, log search, deploy system, distributed cron, multi-region
failover). Scored on: requirements gathering, scale estimation with real numbers, component
design, **failure-mode analysis**, trade-off articulation, and observability. The best
candidates spend a third of the time on "what breaks and what happens then".

## The 45-minute shape
1. **Requirements (5 min)** — functional (what it must do), non-functional (latency,
   availability target, consistency, durability, retention), constraints (budget, team,
   existing infra). Write them down. Ask what's out of scope.
2. **Estimate (3 min)** — QPS (avg and peak, ~3-5x), payload size, storage/day and per
   year, bandwidth, number of hosts. Say the assumption, do the arithmetic aloud.
3. **High-level design (10 min)** — boxes and arrows: clients → edge → services → storage →
   async. Name the data flow for the main path.
4. **Deep dive (15 min)** — the 1-2 hardest components; data model, partitioning,
   consistency, hot paths.
5. **Failure modes & operations (10 min)** — each component: what if it's slow, down,
   partitioned, wrong? Degradation behaviour, backpressure, capacity, deploy safety.
6. **Observability & wrap-up (2 min)** — SLIs, dashboards, alerts, runbooks; what you'd
   build first and what you'd cut.

## Numbers every estimate leans on
- 1 day ≈ 86,400 s ≈ 10⁵ s. 1M req/day ≈ 12 QPS. 100M/day ≈ 1,200 QPS.
- Memory ~100 ns, SSD read ~100 µs, disk seek ~10 ms, same-DC RTT ~0.5 ms, cross-region
  RTT 50–150 ms, 1 MB over 1 Gbps ≈ 10 ms.
- A commodity host: tens of thousands of simple RPS; a Postgres primary: ~10k simple
  writes/s; Redis: ~100k ops/s; Kafka partition: tens of MB/s.
- 99.9% = 8.7 h/year down; 99.99% = 52 min; 99.999% = 5 min.

## Building blocks and when to use them
| Need | Tool | Watch out for |
|---|---|---|
| distribute load | L4/L7 LB, anycast, DNS | health checks, connection draining, sticky sessions |
| read scaling | cache (cache-aside, write-through), replicas | invalidation, stampede, replica lag |
| write scaling | sharding/partitioning by key | hot shards, resharding, cross-shard txns |
| decoupling & smoothing | queue / log (Kafka, SQS) | ordering, at-least-once, consumer lag, DLQ |
| coordination | leases, leader election, fencing tokens | split brain, clock skew, lease expiry |
| rate control | token bucket, leaky bucket, sliding window | fail-open vs fail-closed, distributed accuracy |
| durability | replication (sync/async), WAL, snapshots | RPO vs latency, backup restore tests |
| search / analytics | inverted index, columnar store, TSDB | cardinality, retention tiers, downsampling |
| global availability | multi-AZ, multi-region active-passive/active-active | data conflicts, failover automation, cost |

## Consistency & data
- **CAP in practice**: during a partition choose availability or consistency; most infra
  picks per-component. Say which and why.
- **Replication**: sync (RPO 0, higher write latency), async (fast, may lose recent writes).
  Quorum reads/writes (W + R > N).
- **Idempotency** is how you get "exactly once": at-least-once delivery + idempotency key +
  dedupe store. Say this whenever exactly-once is requested.
- **Partitioning key** choice decides hot spots; hash for spread, range for locality.
- **Schema/migrations**: expand → migrate → contract; backward-compatible deploys.

## Failure-mode checklist (run it per component)
- Slow (not down) — timeouts, bulkheads, circuit breakers, hedged requests?
- Down — retry with backoff + jitter, failover, degrade gracefully (serve stale, shed load)?
- Partitioned — split brain? fencing? what's the source of truth?
- Overloaded — backpressure, queue bounds, load shedding, priority/QoS, autoscaling lag?
- Wrong — bad deploy: canary, gradual rollout, automatic rollback; bad data: validation, DLQ.
- Correlated failure — same AZ, same dependency, same deploy, thundering herd at recovery.
- Recovery — cold cache, backlog drain, retry storm; make recovery *safe*.

## Operability (this is where PE candidates win)
- **SLIs/SLOs** — pick 2-3 (availability, latency p99, freshness). Error budget drives
  release pace.
- **Observability** — RED (rate, errors, duration) per service; USE (utilisation,
  saturation, errors) per resource; structured logs with request IDs; traces across hops.
- **Alert on symptoms** (user-visible SLO burn), page on urgency, ticket the rest.
- **Deploy safety** — canary, staged rollout, feature flags, one-click rollback, config as
  code, immutable artifacts.
- **Capacity** — headroom target (e.g., 50%), N+1/N+2 per failure domain, load tests,
  growth forecast.
- **Cost** — say roughly what dominates (storage vs compute vs egress) and one lever.

## Trade-off vocabulary (use explicitly)
Latency vs consistency · availability vs correctness · simplicity vs flexibility ·
cost vs durability · accuracy vs throughput (sampling, sketches) · build vs buy ·
push vs pull · sync vs async · centralised vs per-host state.

## Common mistakes
- Skipping requirements and estimates, then designing for the wrong scale.
- Drawing every box you know (Kafka + Redis + K8s) without a reason for each.
- No failure analysis; no numbers; no SLO; "we'd just scale it".
- Claiming exactly-once, strong consistency everywhere, or zero downtime for free.
- Not finishing: ran out of time before the hard part. Manage the clock aloud.

## Practice prompts
- Distributed rate limiter at 1M QPS. / Metrics pipeline at 10M points/s.
- Log search for 50k hosts, 30-day retention. / Deploy system for 100k servers.
- Distributed cron with exactly-once semantics. / Multi-region failover, RTO 5 min.
- Health-checking and alerting system for a 200k-host fleet.
- Secrets distribution to every host with rotation and audit.
