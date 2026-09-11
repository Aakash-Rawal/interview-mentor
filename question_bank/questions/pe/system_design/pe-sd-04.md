---
id: pe-sd-04
domain: pe
topic: system_design
difficulty: medium
tags: [deploys, rollout, safety]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a deployment system that can roll a new binary to 100,000 servers safely.

## What interviewers look for
- Designs the rollout as a control loop with explicit gates and bake times, not just a sequence of percentages
- Separates artifact distribution scaling from rollout orchestration — two different problems
- Thinks in failure domains (AZ, rack, shard, cell) rather than flat percentages of hosts
- Names the failure modes that staged rollout does NOT catch and what covers them
- Treats rollback as a first-class, tested, fast path including config and schema

## Strong answer covers
1. Staged rollout with gates: single canary host → 1 host per failure domain → 1% → 5% → 25% → 50% → 100%, each with a bake time long enough to see the signal (minutes for crash loops, tens of minutes to hours for memory leaks and cron-triggered paths), and a hard rule that promotion is automatic only if health gates pass
2. Health signals for the gate: process up/crash-loop count, RED metrics on the canary (error rate, p99 latency) compared statistically against a control group rather than a fixed threshold, SLO burn rate, resource saturation (RSS, fd count, GC), dependency error rates, and log error-pattern deltas. Automatic halt on gate breach; automatic rollback on severity
3. Artifact distribution: 100k hosts × e.g. 500 MB = 50 TB of transfer; a single origin at 10 Gbps takes ~11 hours, so use CDN/regional mirrors or peer-to-peer (torrent-style) distribution, content-addressed artifacts with checksums and signatures, pre-staging the binary on hosts before the activation step so the cutover is a fast symlink swap
4. Agent design: pull-based, idempotent converge-to-desired-state agents (declare version, reconcile) so retries and duplicate instructions are safe, exponential backoff with jitter on failure, and a local safety interlock — refuse to restart if the host is the last healthy replica or if draining fails
5. Concurrency limits per failure domain: never more than X% of any AZ/rack/shard/service replica set in flight, respect minimum-available quotas, serialise across leader/replica roles, and stagger cron-heavy or stateful tiers
6. Failure modes staged rollout misses: slow-burn leaks and latent bugs triggered only at scale or by rare inputs (mitigate with long bake at 1-5%, soak environments, and shadow traffic), correlated config+binary changes (deploy them separately), data/schema changes (expand → migrate → contract, backward-compatible readers first), and 'the 100% step is the dangerous one' because full load only appears then
7. Rollback: previous artifact kept on disk for instant revert, one-click/automatic rollback with the same staged mechanism, an explicit statement that some changes are not rollback-safe (migrations, cache format changes, message schema) and require forward-fix plus feature flags to decouple deploy from release
8. Safety, audit and process: dry-run/plan mode showing which hosts would change, signed artifacts and verified provenance, immutable versioned deploy specs as code, full audit trail of who deployed what where and when, a global 'freeze / emergency stop' button, and rate-limiting concurrent independent rollouts so two teams don't jointly break a shared dependency
9. Operational metrics: rollout progress and duration, hosts by version (an important dashboard — version skew visibility), failed-converge count, rollback count and MTTR, and an alert on hosts stuck on an old version for days

## Follow-ups
- A bug only manifests under full production load, so it passes every stage and breaks at 100%. How do you reduce that risk without doubling rollout time?
- The deploy control plane is down and you need to ship an emergency security fix to all 100k hosts. What do you do?
- How do you handle a binary change that requires a coordinated, non-backward-compatible wire protocol change between two services?
- How would you decide the bake time at each stage from data rather than intuition?

## Sample answer
Two separate problems: getting bits to 100k hosts, and deciding whether to keep going. For distribution, 100k × 500 MB is 50 TB — a single origin at 10 Gbps would take half a day, so content-addressed, signed artifacts served via regional mirrors or peer-to-peer, pre-staged on the host so activation is just a fast swap. The agent is pull-based and converges to a declared desired version, which makes every instruction idempotent and retry-safe; it backs off with jitter and refuses to restart if it'd take the last healthy replica in a shard. Orchestration is a control loop with gates: one canary, then one host per failure domain, then 1%, 5%, 25%, 100%, with bake times and concurrency caps of a few percent per AZ and shard. Gates compare canary RED metrics against a control group statistically, plus crash loops, RSS growth, fd counts and SLO burn — breach halts automatically, severity rolls back automatically. I'd keep the previous artifact on disk for instant revert, and separate binary from config from schema changes: schema goes expand-migrate-contract, and risky behaviour hides behind flags so release is decoupled from deploy. What staging misses is slow leaks and full-load-only bugs, so I'd bake long at 5% and be most careful at the last step. Dashboards: hosts by version, stuck hosts, rollout duration, rollback MTTR.
