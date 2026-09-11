# Coding — Production Engineering / SRE

## What this interview actually tests
PE coding is not LeetCode. The interviewer wants to see you handle **real operational data**
(logs, metrics, process lists, config files) correctly, safely, and at scale, while
talking. Typical shape: parse or aggregate a large input, then a twist (memory limit,
streaming, top-K, concurrency, a second requirement). Scored on: clarifying the input,
choosing a data structure and saying why, correctness, edge cases, complexity stated
unprompted, memory safety, and narration.

## The 6-step answer shape (use it every time)
1. **Clarify the input** — format, size (fits in memory?), encoding, malformed lines, sorted?
2. **State the approach and data structure before code** — "one pass, a dict keyed by IP,
   because we need O(1) increments".
3. **Write the simple correct version** — no premature optimisation.
4. **Walk one example through it** out loud.
5. **Edge cases** — empty input, one line, huge file, negatives/zeros, duplicates, unicode,
   trailing newline, a field missing.
6. **Complexity and scale-up** — time, space, then "if it doesn't fit: shard / external sort /
   streaming / approximate".

## Patterns you must be able to write cold (Python)
### Streaming a file
```python
with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:                      # constant memory, never f.read()/readlines()
        parts = line.rstrip("\n").split()
        if len(parts) < 7: continue     # malformed: skip and count, don't crash
```
### Counting / grouping
```python
from collections import Counter, defaultdict
hits = Counter(); by_status = defaultdict(list)
hits[ip] += 1; by_status[code].append(latency)
```
### Top-K
```python
import heapq
heapq.nlargest(5, hits.items(), key=lambda kv: kv[1])   # O(n log k)
```
A min-heap of size K for streaming top-K; `heapq` is a **min**-heap, negate for max.
### Running aggregates
Average = sum/count; percentiles need all values (or a sketch: t-digest, HdrHistogram).
Running median = two heaps. Running max/min over a window = monotonic deque.
### Sliding window over time
`collections.deque` of timestamps; pop-left while `ts < now - window`.
### Sort vs heap vs dict
| Need | Structure | Cost |
|---|---|---|
| exact count by key | dict / Counter | O(1) per op |
| top-K of n | heap of size K | O(n log K) |
| full ordering | sort | O(n log n) |
| membership / dedup | set | O(1) |
| ordered by insertion + O(1) evict | OrderedDict / dict + linked list | LRU |
| range queries on sorted data | bisect | O(log n) |
### Lazy deletion
Mark entries dead instead of removing from a heap; skip dead ones on pop. Standard
trick for "remove arbitrary item from a priority queue".

## Complexity you should state without being asked
- dict/set: O(1) average, O(n) worst; list index O(1), search O(n), insert front O(n)
- heap push/pop O(log n), peek O(1); building a heap from a list O(n)
- sort O(n log n), Timsort is stable and O(n) on nearly-sorted input
- string concatenation in a loop is O(n²): use `"".join(parts)`

## Memory-safety habits interviewers listen for
- Never `read()` a file you haven't sized. Never build a list just to count it.
- Generators over lists: `sum(1 for _ in f)`, `max(map(f, it))`.
- "Unique IPs might not fit either" → hash-partition to k files, process each; or a
  Bloom filter for "seen before"; or an external sort + merge.
- Be explicit about what you keep in memory and why it's bounded.

## Concurrency questions (they come up)
- Python threads share the GIL: fine for I/O-bound (network, disk), not CPU-bound —
  use processes or offload. `concurrent.futures` is the idiomatic answer.
- Protect shared state with a lock; prefer per-worker aggregation then a merge.
- Backpressure: bounded queues, not unbounded lists.

## Robustness details that separate senior candidates
- Timeouts on every network call; retries with exponential backoff **and jitter**; retry
  only idempotent operations; respect `Retry-After`.
- Exit codes and stderr for tools; structured logs; don't swallow exceptions silently.
- Malformed input is normal: count it, log a sample, keep going, report at the end.
- Don't mutate a collection while iterating it.

## Common mistakes
- Jumping into code before confirming the input size and format.
- `readlines()` on a multi-GB file; `sorted(...)[:5]` instead of a heap for top-K.
- Forgetting the empty-input path (divide by zero, `max()` of empty sequence).
- Saying "O(n)" without saying n is what — lines? bytes? unique keys?
- Going silent while typing. Narrate: "now I need to handle the case where…".

## What a strong candidate says
- "Before I code: how big is this and does it fit in memory?"
- "I'll use a Counter because we need O(1) increments per key; then a size-5 heap."
- "Edge cases I'll handle: empty file, malformed line, a field that isn't numeric."
- "This is O(n) over lines and O(u) memory in unique keys; if u is too big I'd shard by hash."

## Practice prompts (self-test)
- Average of a field over a 40 GB log; then p99 of that field.
- Top 10 URLs by 5xx count in the last 15 minutes from a live tail.
- Detect clients making more than 100 requests/min from a stream.
- Merge two sorted 20 GB files into one sorted output with 1 GB RAM.
- Parse `/proc/<pid>/status` for every PID and rank by RSS.
