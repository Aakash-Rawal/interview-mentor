---
id: pe-cod-05
domain: pe
topic: coding
difficulty: medium
tags: [rate-limiting, data-structures]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Implement a sliding-window rate limiter: allow at most N requests per client per 60s. It must be called on every request with low overhead.

## What interviewers look for
- Asks whether the limiter is per-process or distributed, and whether exactness or cheapness matters more
- Picks a structure and defends it — deque for exact sliding window, counters for approximate
- Raises unbounded memory from idle clients unprompted and proposes eviction
- Thinks about the concurrency story: lock scope, per-key locking, or sharding
- Compares sliding-window-log, sliding-window-counter, and token bucket by cost and accuracy

## Strong answer covers
1. Exact approach: `dict[client] -> collections.deque` of request timestamps; on each call pop from the left while `ts <= now - 60`, then allow if `len(dq) < N` and append now — amortised O(1) per request, O(N) memory per active client
2. Approximate alternative: fixed-window counters with two buckets (current and previous minute), weighting the previous bucket by the fraction of the window it still covers — O(1) memory per client, bounded error, no per-request timestamp list
3. Contrast with token bucket / leaky bucket: two floats per client (tokens, last_refill), O(1) memory and time, allows configurable burst — usually the right production choice
4. Memory growth from idle clients is called out: unbounded dict keyed by client. Fixes: LRU/TTL eviction of entries whose deque is empty, periodic sweep, or a bounded LRU cache with a max entry count
5. Thread safety: a global lock serialises every request and becomes the bottleneck; use a per-client lock or shard the map by `hash(client) % k` with k locks, keeping the critical section to a few operations
6. Clock concerns: use a monotonic clock (`time.monotonic`) for window arithmetic so NTP steps or leap-second smearing can't let traffic through or lock clients out; wall clock only for logging
7. Distributed case: per-process limiting means N × number_of_instances actual rate; a shared store (Redis with INCR+EXPIRE, or a Lua script for atomicity) or a coordinated token bucket is needed, at the cost of a network hop per request
8. Behaviour on limit: return a decision plus retry-after hint (429 semantics), emit a metric for allowed/denied per client, and fail open or closed deliberately if the shared store is unavailable

## Follow-ups
- Your service runs on 40 pods behind a load balancer. Each enforces 100/min locally. What does the client actually experience, and how do you fix it?
- One client is hammering you with 50,000 requests per minute. What does your exact-deque implementation cost, and what do you switch to?
- How would you allow short bursts — 200 in a second is fine, but not 10,000 in a minute?
- The shared Redis for limiting goes down. Fail open or fail closed, and how do you make that decision safely?

## Sample answer
First: is this per-process or fleet-wide, and do we need exactly 100 or approximately 100? For a single process with exactness required, I keep a dict from client to a deque of timestamps. On each call I take monotonic now, pop from the left while the front is older than now minus 60, then allow if the deque is shorter than N and append. That's amortised O(1) and gives a true sliding window, but it costs up to N timestamps per active client — a client sending fifty thousand a minute costs me fifty thousand entries, which is where I'd switch to counters. The cheap version is two fixed-window counters, current and previous minute, with the previous weighted by how much of the window it still covers: constant memory, a few percent of error. Honestly in production I usually reach for a token bucket — two floats per client, O(1), and it gives me burst control for free. Two things I'd raise unasked: the dict grows forever with idle clients, so I need TTL or LRU eviction; and a single global lock serialises every request, so I'd shard the map by key hash across k locks. If this must hold fleet-wide, local counters give N times the pod count, so it has to move to a shared store with an atomic increment-and-expire.
