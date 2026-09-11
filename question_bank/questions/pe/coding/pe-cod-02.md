---
id: pe-cod-02
domain: pe
topic: coding
difficulty: medium
tags: [hash-map, top-k, heap]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Find the top 5 client IPs by request count in an access log that may be tens of GB.

## What interviewers look for
- Separates the two phases: O(1) counting per line, then top-K selection
- Chooses a heap over a full sort for top-K and can justify O(n log k) versus O(n log n)
- Distinguishes memory in lines (bounded) from memory in unique keys (unbounded) and quantifies it
- Offers concrete fallbacks — hash sharding, external sort, count-min sketch — with trade-offs
- Narrates while coding and covers malformed lines and ties

## Strong answer covers
1. One streaming pass with `collections.Counter` (or defaultdict(int)) keyed by IP because increments must be O(1); extracts the IP as the first whitespace field after confirming the format
2. Top-5 via `heapq.nlargest(5, hits.items(), key=lambda kv: kv[1])` — O(n log k) — and explicitly contrasts with `sorted(...)[:5]` which is O(n log n) over unique keys
3. States complexity precisely: O(n) time in log lines, O(u) memory in unique IPs; estimates u — e.g. a few million IPv4 addresses at ~100 bytes per dict entry is a few hundred MB, which is fine; a billion is not
4. If unique keys don't fit: hash-partition lines into k files by `hash(ip) % k` so all occurrences of an IP land in one file, count each file independently, then merge the per-file top-5s into a global top-5
5. Alternative: `sort | uniq -c | sort -rn | head -5` using external merge sort (GNU sort spills to disk), or an approximate count-min sketch / Space-Saving heavy-hitters algorithm with bounded memory and stated error
6. Handles malformed or empty lines by skipping and counting; mentions that proxy logs may need X-Forwarded-For rather than the connecting IP
7. Discusses ties at the boundary (two IPs with equal counts) and that nlargest is deterministic on the underlying order but ties should be documented
8. Notes parallelism: per-shard Counters merged with `Counter.update` is embarrassingly parallel and correct because counting is associative

## Follow-ups
- Now it's a live tail, not a file, and I want the top 5 over the last 15 minutes only. What changes?
- A single IP is 90% of traffic and your dict is fine, but the job still takes hours. Where's the time going and how do you speed it up?
- Can you do exact top-K in sublinear memory? Argue why or why not.
- How would you expose this as a recurring job with alerting on a new entrant to the top 5?

## Sample answer
Before coding: how big, what's the line format, and roughly how many unique IPs? Size of the file doesn't scare me — I stream it — but unique IPs determine my memory. Plan: one pass, a Counter keyed by IP because I need O(1) increments, then `heapq.nlargest(5, hits.items(), key=itemgetter(1))`. That's O(n) over lines plus O(u log 5) for selection, and O(u) memory. I'd avoid `sorted(counts)[:5]` — that's an unnecessary n log n over every unique key. Malformed lines get skipped and counted. If there are a few million IPs, a dict is a few hundred megabytes and I'm done. If unique IPs don't fit, I hash-partition: write each line to one of, say, 256 spill files by `hash(ip) % 256`, which guarantees all occurrences of an IP land in the same file, count each file with the same code, and merge the per-file top-5s. The shell equivalent is `awk '{print $1}' | sort | uniq -c | sort -rn | head`, which uses external merge sort. If approximate is acceptable, Space-Saving or count-min gives heavy hitters in fixed memory with a bounded error — I'd say so and let the requester choose.
