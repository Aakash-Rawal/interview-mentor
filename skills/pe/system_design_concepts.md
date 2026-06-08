# System Design Concepts (PE / SRE)

## CAP theorem
Under a network partition you choose Consistency or Availability. PE framing:
most large systems pick AP with eventual consistency and reconcile. Know when
you genuinely need CP (e.g. leader election, financial ledgers).

## Caching strategies
- **Cache-aside (lazy)** — app reads cache, on miss loads DB then populates. Simple, risk of stale.
- **Write-through** — write cache + DB together; consistent, slower writes.
- **Write-back** — write cache, async flush; fast, risk of loss.
- **TTL + jitter** — avoid synchronized expiry (thundering herd on cache).
- Eviction: LRU default; LFU for skewed popularity.

## Database choices
| Need | Pick |
|---|---|
| Strong relational, transactions | PostgreSQL / MySQL |
| High write throughput, wide rows | Cassandra |
| Key-value, low latency | Redis / DynamoDB |
| Full-text search | Elasticsearch |
| Time-series metrics | Prometheus / InfluxDB |

## Failure modes to design against
- Cascading failure → bulkheads, circuit breakers, load shedding.
- Retry storms → exponential backoff + jitter, retry budgets.
- Single points of failure → replication, multi-AZ, failover.
- Hot shards → consistent hashing, key salting.

## Observability (the three pillars)
- **Metrics** — RED (Rate, Errors, Duration) / USE (Utilization, Saturation, Errors).
- **Logs** — structured, sampled at high volume.
- **Traces** — distributed tracing for cross-service latency.
Define SLIs → SLOs → error budgets. Alert on symptoms (user-facing), not causes.

## Interview behaviour
Start with requirements + scale estimates (QPS, data size). State assumptions.
Draw the happy path, then attack it with failure scenarios.
