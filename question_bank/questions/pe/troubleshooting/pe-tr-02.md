---
id: pe-tr-02
domain: pe
topic: troubleshooting
difficulty: medium
tags: [incident, rollback]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Error rate for a service jumps from 0.1% to 15% ten minutes after a deploy. You're on call. Walk me through the first 15 minutes.

## What interviewers look for
- Mitigates before diagnosing, and explicitly checks whether rollback is safe and reversible
- Gets numbers and dimensions (which endpoints, which hosts, which region) instead of theorising
- Explains the 10-minute lag rather than assuming instant causation
- Communicates: declares an incident, assigns roles, updates stakeholders
- Verifies recovery with the metric and names concrete prevention (canary with auto-rollback)

## Strong answer covers
1. Characterise in the first two minutes: 15% of what absolute volume, which status codes (5xx vs 4xx vs timeouts), which endpoints, which clients, and is it stable or still climbing; is user-visible impact confirmed (checkout failing) or only internal errors
2. Confirm correlation with the deploy by slicing by version/host: are errors only on hosts running the new build, and did they start as the rollout crossed a percentage? If errors are uniform across old and new hosts, the deploy may be a coincidence or a trigger of a latent limit, not the cause
3. Mitigate first with the most reversible lever: feature flag off if the change is flagged, otherwise roll back / shift traffic to the previous version; state the blast radius check — did the release include a schema migration, a backfill, a cache-format or message-format change that makes rollback non-reversible? Confirm with the data owner if so
4. Explain the 10-minute delay: gradual/canary rollout reaching a threshold, connection pools or caches warming, a TTL expiring, a cron or scheduled job firing, leaked resource (fds, memory, connections) crossing a limit, or old instances still draining
5. Declare the incident and communicate: incident channel, IC/comms roles, status page or stakeholder update with impact and ETA, and a note that investigation continues after mitigation
6. Evidence before and during: grab a sample of the new error strings and stack traces, request IDs, the deploy diff and changelog, and keep one new-version host out of rotation (or a copy of its logs/heap) so rollback doesn't destroy the evidence
7. Verify: watch error rate return to ~0.1% within a few minutes, confirm latency and downstream metrics recovered, check for a retry backlog or queue drain causing a second spike, and hold the change freeze until root cause is understood
8. Prevention with owners: canary deploy with automated error-rate comparison and auto-rollback, deploy markers on dashboards, per-version error dashboards, alert on error-rate ratio not absolute, a regression test reproducing the failing request, and a rollback-safety checklist for migrations

## Follow-ups
- You roll back and the error rate stays at 15%. What are your next three hypotheses and how do you test them cheaply?
- The release included a migration that added a NOT NULL column with a default. How does that change your mitigation plan?
- Errors are 15% in one region and 0.1% everywhere else, but the deploy went everywhere. What does that tell you?
- Write the postmortem action items: which one reduces detection time, which reduces mitigation time, and how would you measure that they worked?

## Sample answer
Minute zero: declare an incident, take IC, and get a number — 15% of what volume, which status codes, which endpoints, stable or climbing. In parallel someone slices errors by build version and host: if only new-version hosts are erroring, that's strong causation; if it's uniform, the deploy may be a trigger rather than the cause.

Minute two to five: mitigate with the most reversible lever. If the change is behind a flag, flip it. Otherwise roll back — but first I ask whether rollback is safe: did this release include a schema migration, a backfill, or a cache/message format change? If yes I bring in the data owner before rolling back, and consider shifting traffic to the old version instead.

While rollback runs I capture evidence — sample stack traces, request IDs, the diff — and I keep one new-version host out of rotation for forensics so rollback doesn't erase the scene. I'd also explain the 10-minute lag: canary percentage crossing a threshold, a pool or cache warming, a cron firing, or a leak hitting a limit.

Minute ten to fifteen: verify error rate is back to 0.1%, watch for a retry-driven second spike, update stakeholders, freeze deploys. Afterwards: canary with automated error comparison and auto-rollback, deploy markers on dashboards, and a regression test for the failing request.
