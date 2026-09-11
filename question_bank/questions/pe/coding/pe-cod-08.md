---
id: pe-cod-08
domain: pe
topic: coding
difficulty: hard
tags: [lru, cache, linked-list]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design and implement an LRU cache with O(1) get and put. Then: how would you make it safe for use from multiple threads without serialising every call?

## What interviewers look for
- Explains why the hash map plus doubly linked list gives O(1) for both operations before coding
- Gets the eviction and move-to-front bookkeeping right, including updating an existing key
- Recognises that a get mutates recency, which is why read-write locks buy little
- Proposes sharding/striping with a concrete contention argument, not just 'add more locks'
- Discusses what correctness guarantees are actually needed — exact LRU vs approximate

## Strong answer covers
1. Structure: dict from key to node, plus a doubly linked list with sentinel head/tail; get = dict lookup then unlink and re-insert at head; put = update in place and move to head, or insert and evict from the tail when over capacity — both O(1) worst case
2. Mentions `collections.OrderedDict` with `move_to_end(key)` and `popitem(last=False)`, or `functools.lru_cache` for the memoisation case, as the idiomatic shortcuts
3. Edge cases handled: capacity 0 or 1, put of an existing key must not grow size or double-insert, get of a missing key returns a sentinel/None distinguishable from a cached None, eviction must delete from both the dict and the list or you leak
4. Concurrency baseline: one mutex around every get and put is correct and simple; every operation becomes serialised, so throughput is capped at one core's worth of lock hold time and the lock becomes the hot spot under load
5. Explains why a read-write lock doesn't help: a cache hit reorders the recency list, so reads are writes to the metadata; you'd have to give up exact recency to make reads truly read-only
6. Sharding/striping: split into k independent caches selected by `hash(key) % k`, each with its own lock and its own capacity/capacity//k; contention drops roughly k-fold for uniformly distributed keys, at the cost of per-shard hit-rate imbalance and only approximate global LRU
7. Alternatives that avoid ordering writes on the read path: CLOCK/second-chance or approximate LRU with a per-entry timestamp or reference bit updated non-atomically, TinyLFU/W-TinyLFU as used by modern caches, or sampled eviction (pick a few random entries, evict the oldest)
8. Python-specific note: the GIL makes dict operations atomic so a naive cache is memory-safe but the multi-step LRU update is not atomic without a lock; and for a CPU-bound workload threads won't scale anyway — processes or a shared external cache are the real answer
9. Mentions operational concerns: metrics for hit rate, size and evictions; a hot key or a scan-heavy workload can thrash LRU, which is an argument for admission policies

## Follow-ups
- Add a TTL per entry. How do you expire lazily versus with a background sweeper, and what does each cost?
- Your hit rate drops from 90% to 40% after a deploy. How do you diagnose whether it's the cache or the traffic?
- One key gets 50% of all lookups and lands in one shard. What happens and what do you do?
- How would you implement LFU instead, and when is it the better policy for a production cache?

## Sample answer
Classic answer: a dict from key to node plus a doubly linked list with head and tail sentinels. The dict gives O(1) lookup; the list gives O(1) unlink and re-insert, so get moves the node to the head and put either updates and moves, or inserts at the head and evicts the tail when I'm over capacity. The bugs to avoid are forgetting to delete the evicted key from the dict, and letting a put of an existing key grow the size. In Python I'd normally just use OrderedDict with move_to_end and popitem(last=False). On threads: a single mutex around get and put is correct, and that's where I'd start — correct first. The reason it hurts is that every cache hit mutates the recency list, so reads are writes and a read-write lock buys almost nothing. The standard fix is striping: k independent shards chosen by key hash, each with its own lock and capacity, which cuts contention roughly k-fold. The trade-off is that global LRU becomes approximate and a hot shard can still be a bottleneck. If I need reads to be genuinely cheap, I'd relax exactness — CLOCK with a reference bit, or a per-entry timestamp and sampled eviction, which is what Redis does. And I'd instrument hit rate and evictions, because an LRU that's being scanned is worse than no cache.
