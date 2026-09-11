---
id: pe-cod-03
domain: pe
topic: coding
difficulty: medium
tags: [heap, streaming]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Maintain the running median of request latencies arriving as a stream.

## What interviewers look for
- Names the two-heap invariant before writing code and states it as an invariant
- Handles even/odd sizes and the rebalance step correctly on the first attempt
- Knows heapq is a min-heap and negates values for the max side
- Volunteers the scale limit — unbounded memory over an infinite stream — and names a sketch
- Walks a short numeric example through the structure out loud

## Strong answer covers
1. Two heaps: `lo` as a max-heap of the lower half (Python's heapq is a min-heap, so push negated values) and `hi` as a min-heap of the upper half
2. Invariant stated explicitly: every element in lo <= every element in hi, and 0 <= len(lo) - len(hi) <= 1
3. Insert algorithm: push onto one heap, then move the extreme element across, then rebalance sizes; correctness hinges on doing the cross-push before the size fix
4. Median read: if sizes are unequal, `-lo[0]`; if equal, `(-lo[0] + hi[0]) / 2` — O(1) peek, O(log n) insert
5. Empty stream returns None rather than raising IndexError on `lo[0]`; single-element case works via the same branch
6. Memory is O(n) in all values seen — unbounded for a never-ending latency stream; fix is a fixed window (ring buffer plus lazy deletion from the heaps) or a bounded sketch
7. Approximate alternatives at scale: t-digest or HdrHistogram give p50/p99 in fixed memory with bounded relative error, and are mergeable across hosts, unlike a median
8. Notes that medians (and percentiles) can't be averaged across shards, which is why sketches that merge matter in monitoring pipelines

## Follow-ups
- Make it a median over the last 10,000 samples only. How do you remove an arbitrary element from a heap?
- I want p99, not p50, from the same stream. Does the two-heap trick generalise?
- You're computing this per-host and need a fleet-wide p50. What breaks?
- How would you test this implementation so you trust it?

## Sample answer
Running median is the classic two-heap problem. I keep `lo`, a max-heap of the smaller half — negated because heapq is a min-heap — and `hi`, a min-heap of the larger half. The invariant is that everything in lo is at most everything in hi, and lo's length is equal to hi's or exactly one more. To insert, I push to lo, then pop lo's max into hi, then if hi got bigger than lo I pop hi's min back into lo. That ordering keeps the invariant regardless of where the value lands. Median is then lo's top if the sizes differ, otherwise the average of the two tops — O(1) read, O(log n) insert. Empty stream returns None, not an IndexError. The catch operationally: memory grows with every sample, so on a real latency stream this is unbounded. I'd either bound it to a sliding window — a deque of arrivals plus lazy deletion, skipping dead entries on pop — or, more likely for monitoring, use a t-digest or HdrHistogram: fixed memory, bounded error, and crucially mergeable across hosts, which raw medians are not.
