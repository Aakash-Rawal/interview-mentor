---
id: pe-cod-10
domain: pe
topic: coding
difficulty: medium
tags: [retry, backoff, resilience]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Write a function that calls a flaky HTTP endpoint with retries. Make it production-grade.

## What interviewers look for
- Distinguishes what is safe to retry from what is not, and asks about idempotency before retrying anything
- Includes jitter and explains the thundering-herd failure it prevents
- Bounds both attempt count and total elapsed time, and sets per-attempt timeouts
- Thinks beyond one call: retry budgets, circuit breakers, and the effect of retries on an already-overloaded dependency
- Instruments it — per-attempt metrics/logs, surfaces the final error with context

## Strong answer covers
1. Retry only on retryable conditions: connection errors, read timeouts, 429, and 5xx except those known to be non-retryable; never retry 4xx like 400/401/403/404, and only retry non-idempotent methods (POST) if there's an idempotency key or the server guarantees it
2. Exponential backoff with jitter: `sleep = min(cap, base * 2**attempt)` then randomise — full jitter `random.uniform(0, sleep)` or decorrelated jitter — and explains that without jitter, N clients retry in lockstep and re-synchronise load onto a recovering service
3. Two independent bounds: max attempts (e.g. 4) and a total deadline for the whole operation, so a chain of retries can't blow past the caller's own SLO; the deadline shrinks each per-attempt timeout
4. Per-attempt timeouts on every network call — both connect and read, e.g. `requests.get(url, timeout=(2, 5))` — and never an unbounded default; explains that a hung call with no timeout is worse than a fast failure
5. Honours `Retry-After` on 429/503 (seconds or HTTP-date), taking the max of it and the computed backoff, and never retries faster than the server asked
6. Observability: log or emit a metric per attempt with status, latency and attempt number; on final failure raise/return an error that names the URL, attempt count, elapsed time and last status, and never swallow the exception silently
7. Server-side sympathy: retries multiply load exactly when the dependency is struggling, so mention a retry budget (cap retries to a small percentage of requests), a circuit breaker that trips after a failure threshold and half-opens to probe, and load shedding rather than infinite client persistence
8. Practical implementation notes: reuse a connection pool / `requests.Session` with an HTTPAdapter and urllib3 Retry, or a library like tenacity, rather than hand-rolling; make the sleep interruptible/cancellable and propagate cancellation; avoid retrying inside a loop that's already being retried by a caller (nested retry amplification)
9. Distinguishes retries from hedging/fallbacks and notes that for reads a stale cache fallback often beats a third retry

## Follow-ups
- The endpoint is a POST that charges a customer. How do you make retrying it safe?
- Every client in your fleet has this retry logic and the dependency has a 30-second brownout. Model what happens to it.
- Where do you put the deadline when this call is three services deep in a request chain?
- How do you test the retry path — including the backoff timing — in CI without sleeping for real?

## Sample answer
First question: is the operation idempotent? If it's a GET or has an idempotency key, I'll retry; if it's a bare POST that mutates state, retrying can double-charge someone, so I'd rather fail. Then: I classify errors. Timeouts, connection resets, 429 and most 5xx are retryable; 400, 401, 403, 404 are not — retrying a bad request just wastes everyone's time. Every attempt gets an explicit connect and read timeout, because a call with no timeout is the worst failure mode. Backoff is exponential with a cap, and crucially with jitter — full jitter, a random sleep between zero and the computed delay. Without jitter, a thousand clients all retry at the same instant and hammer the service the moment it starts recovering. If the response carries Retry-After, I honour it and take the max of that and my backoff. I bound both the attempt count and a total deadline, so retries can't exceed the caller's own budget, and each attempt's timeout is clipped to the remaining deadline. I emit a metric and log line per attempt, and on final failure I raise an error naming the URL, attempts, elapsed time and last status rather than swallowing it. Beyond one function, retries amplify load during an outage, so I'd add a retry budget and a circuit breaker — and in practice I'd use a Session with urllib3's Retry or tenacity rather than hand-rolling this.
