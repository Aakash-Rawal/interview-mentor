---
id: pe-sd-05
domain: pe
topic: system_design
difficulty: hard
tags: [scheduling, idempotency, leases]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a distributed cron: users register jobs with schedules, and each job must run exactly once per tick even if schedulers crash.

## What interviewers look for
- Immediately reframes exactly-once as at-least-once delivery plus idempotent execution with a dedupe store
- Chooses an ownership model (leader election vs sharded partitions) and reasons about blast radius and scale
- Uses leases with fencing tokens and can explain the split-brain scenario they prevent
- Has an explicit missed-run / catch-up policy rather than assuming schedulers never die
- Monitors for the silent failure — a job that never ran — not just failed runs

## Strong answer covers
1. Reframing: true exactly-once execution is impossible across a network/crash boundary; the achievable contract is at-least-once trigger + idempotency key (job_id + scheduled_tick) + a dedupe/claim record in a transactional store, so a duplicate trigger becomes a no-op. Say this out loud, and note the worker must also be idempotent or use a conditional 'claim then execute then mark done' transition
2. Job store: durable, replicated store of job definitions (schedule spec, timezone/DST handling, timeout, retry policy, concurrency policy) plus a run table keyed by (job_id, tick) with a unique constraint — the unique constraint is what actually enforces once-per-tick
3. Ownership model: either single leader (simple, small blast radius of decisions, but a scale and availability bottleneck) or partition job space by hash with per-partition ownership and leader election per partition; compare and pick based on job count. Leader election via Raft/consensus store (etcd/ZooKeeper) lease, not a homegrown lock
4. Leases and fencing: an owner holds a time-bounded lease with a monotonically increasing fencing token; a stalled-then-resumed scheduler (long GC pause, network partition) must have its writes rejected by the store because its token is stale — this is the split-brain case. Lease TTL must exceed worst-case pause, and the safe pattern is: new owner cannot start until old lease is provably expired
5. Clock skew: schedulers must not each trust local clocks for tick boundaries; use NTP with monitoring and skew alerts, derive ticks from the store's authority or accept a tolerance window, and never allow a skewed node to fire ticks early
6. Separation of scheduling and execution: scheduler only enqueues work (to a queue/log with at-least-once semantics); workers execute with visibility timeouts and heartbeats, so a long-running job doesn't block the scheduler and a dead worker's task becomes re-claimable
7. Missed-run policy per job, declared explicitly: skip (don't run stale ticks), run-once-catch-up (run the latest missed tick only), or backfill-all; plus max-catchup-age, and a per-job concurrency policy (allow, forbid, replace) for when a run overruns into the next tick
8. Monitoring for absence: alert on expected-run-not-started within a deadline (freshness/heartbeat per job), running-longer-than-p99, run failure rate, lease flapping / leader election churn, scheduler-to-fire delay p99, and queue depth. Also expose a per-job last-success timestamp and let job owners set their own SLO
9. Overload and thundering herd: many jobs share popular schedules (top of the hour, midnight UTC) — smear with per-job jitter or hashed offsets, cap concurrent dispatches, and rate-limit catch-up storms after an outage so recovery doesn't take down downstream services

## Follow-ups
- A scheduler node pauses for 90 seconds on GC and then resumes and fires its ticks. Walk me through exactly what prevents a double run, at which layer.
- The whole scheduler tier was down for six hours. What runs when it comes back, and how do you keep that from taking out the downstream database?
- A job's side effect is calling a third-party API with no idempotency support. What can you actually promise the user?
- How would you let users test a schedule change safely, and how do you handle DST for a job defined in a local timezone?

## Sample answer
First I'd reset the contract: you can't get exactly-once execution across crashes, so what I'll build is at-least-once triggering plus idempotent execution. Concretely, every run is keyed by job ID plus scheduled tick, and there's a run row with a unique constraint on that pair in a replicated store — that constraint, not the scheduler's cleverness, is what enforces once-per-tick. Schedulers partition job space by hash; each partition has an owner holding a time-bounded lease from a consensus store with a monotonically increasing fencing token. If an owner pauses for a GC and wakes up thinking it's still the leader, its claim write is rejected because its token is stale — that's the split-brain guard. Schedulers only enqueue; workers execute with heartbeats and visibility timeouts, so a slow job doesn't stall the tick loop and a dead worker's task is reclaimable. Each job declares a missed-run policy — skip, catch-up-latest, or backfill with a max age — and a concurrency policy for overruns. I don't trust local clocks: NTP with skew alerts and ticks anchored to the store. The alert I care most about is absence: no successful run within the job's deadline. And I'd jitter schedules, since everyone picks midnight UTC, and rate-limit catch-up after an outage so recovery doesn't melt downstream.
