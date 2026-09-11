# Troubleshooting & Incident Response — Production Engineering / SRE

## What this interview actually tests
Method under ambiguity. The scenario is deliberately vague ("the site is slow"). You are
scored on whether you **characterise before acting**, eliminate systematically, choose the
right tool, read evidence correctly, protect data, apply the simplest safe fix, and frame
prevention fleet-wide. Speed matters less than not thrashing. Mitigate first, root-cause second.

## The 7-step framework (announce it, then follow it)
1. **Characterise** — What exactly is broken, for whom, since when, how bad? Get a number
   (error rate, p99, affected %). Is it getting worse?
2. **What changed?** — Deploys, config, flags, traffic, infra, certs, upstreams, time-based
   jobs. Most incidents follow a change.
3. **Mitigate / stop the bleeding** — Rollback, feature flag off, shed load, fail over,
   scale up. Reversible actions first. Communicate.
4. **Localise** — Which layer? Which component? One host / one AZ / one shard / all?
   Bisect: healthy vs unhealthy comparison is your strongest tool.
5. **Diagnose** — Form hypotheses, rank by likelihood × ease of test, test cheapest first.
   Read the evidence you get; don't hallucinate.
6. **Fix and verify** — Apply the fix, confirm the metric recovered, watch for regression.
7. **Prevent** — Postmortem: detection gap, mitigation time, root cause, action items
   (alerting, guardrails, tests, capacity), fleet-wide not one box.

## Golden discovery questions (ask before touching anything)
- "What does 'slow' mean — latency, errors, timeouts? Which percentile? Since when?"
- "All users or a subset? One region, one client version, one tenant?"
- "What changed in the last hour — deploys, config, traffic, dependencies?"
- "Is it stable, worsening, or oscillating?"
- "Is there a runbook or a previous incident that looks like this?"
- "What's the blast radius if I roll back / restart / fail over?"

## Localisation moves
- **Compare healthy vs unhealthy** — one host vs its peers, one region vs another,
  before vs after. Diff everything: versions, config, kernel, hardware, traffic mix.
- **Follow the request path** — client → DNS → LB → service → cache → DB → downstream.
  Instrument or probe each hop: `curl -w` timings, LB backend health, DB slow log.
- **Layers**: network (loss, latency, DNS), host (CPU, mem, disk, fds), process (GC,
  threads, locks), dependency (DB, cache, queue), data (hot key, big payload, poison message).
- **Correlate on a timeline** — overlay the incident start on dashboards; the first metric
  to move is usually closest to the cause.

## Patterns with named signatures
| Pattern | Signature | Typical fix |
|---|---|---|
| Thundering herd | spike of retries/reconnects right after a blip; cache expiry storms | jittered backoff, request coalescing, staggered TTLs |
| Cascading failure | one dependency slow → threads exhausted → whole service down | timeouts, bulkheads, circuit breakers, load shedding |
| Retry storm | traffic multiplies during an outage | retry budgets, exponential backoff, drop non-idempotent retries |
| Hot key / hot shard | one cache node or DB shard pegged, rest idle | key splitting, local cache, better hashing |
| Connection exhaustion | "too many connections", pool waits | pooler, right-size pools to DB limits, kill idle-in-txn |
| GC pause / stop-the-world | periodic latency spikes, heap sawtooth | heap tuning, allocation fix, more instances |
| Slow-consumer backpressure | queue depth grows, producers time out | scale consumers, drop/aggregate, bounded queues |
| Split brain / stale config | two nodes believe they're primary; nodes disagree | fencing, quorum, config version check |
| Certificate expiry | TLS handshake failures at an exact time, nothing deployed | renew, automate, alert on days-to-expiry |
| DNS TTL / caching | subset of clients still hitting old IP after a change | lower TTL beforehand, keep old endpoint alive |
| Noisy neighbour | %steal, one host in a fleet slow, no code change | migrate, dedicated hosts, report to infra |
| Clock skew | auth/token failures, ordering bugs | NTP/chrony, alert on drift |

## Reading evidence correctly
- A metric that *didn't* change is evidence too. Say what you'd expect to see if the
  hypothesis were true, then check.
- p50 fine + p99 bad → tail: a subset (hot key, one host, GC, retries). Both bad →
  saturation or a dependency.
- Errors before latency → hard failure (deploy, config, dependency down). Latency before
  errors → saturation (timeouts follow queueing).
- Correlation ≠ cause: the deploy that "coincides" might be the trigger, not the root
  (e.g., it exposed a latent capacity limit).

## Data-preservation language
- "Before I restart, I'll snapshot the evidence: logs, `dmesg`, thread dump, connection table."
- "Rollback is reversible; a schema change is not — I'll confirm with the DB owner first."
- "I'll make the change on one host, verify, then roll out."

## Postmortem shape (30 seconds)
Impact (who, how long, how bad) → timeline (detect, mitigate, resolve) → root cause and
contributing factors → what went well / poorly → action items with owners: detection,
mitigation speed, prevention, and a test that would have caught it. Blameless.

## Common mistakes
- Guessing a cause in the first sentence instead of asking what changed.
- Restarting before capturing evidence; fixing one host and calling it done.
- Not mitigating first ("let me find the root cause" while users are down).
- Ignoring the blast radius of the fix (rolling back a migration, failing over a DB).
- Skipping verification: "I applied the fix" without "and the error rate dropped to X".

## Practice prompts
- Error rate 0.1% → 15% ten minutes after a deploy; 20 hosts; walk the first 15 minutes.
- One host in a fleet shows 10x p99; same code, same config.
- Site slow every day 09:00–09:10; nothing in the deploy log.
- DB "too many connections" after scaling the app tier from 10 to 30 instances.
- Intermittent "connection reset" for 2% of requests; nobody can reproduce.
