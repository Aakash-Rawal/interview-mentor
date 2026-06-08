# Coding Patterns (PE / SRE)

PE coding leans on practical data handling, not algorithm trivia. Memory
safety and talking through reasoning matter as much as correctness.

## File I/O patterns
- **Line-by-line reading** — never load a multi-GB log into memory.
  ```python
  with open(path) as f:
      for line in f:        # streams, constant memory
          process(line)
  ```
- **Running aggregates** — compute averages/counts without storing all rows.
  ```python
  total, n = 0, 0
  for line in f:
      total += float(line); n += 1
  avg = total / n if n else 0
  ```

## Hash map counting
- `collections.Counter` for frequency; `dict.get(k, 0) + 1` for manual counts.
- Use for: top-N log sources, dedup, grouping events by key.

## Heaps
- `heapq` for top-K / streaming min/max. A min-heap of size K gives top-K largest.
- `heappush`/`heappop` are O(log n). Use `heapq.nlargest(k, iterable)` for one-shot.

## Lazy deletion
- Mark entries dead instead of removing from a heap/structure mid-iteration;
  skip dead entries on pop. Avoids O(n) removal.

## Complexity reference
| Structure | Lookup | Insert | Notes |
|---|---|---|---|
| list | O(n) | O(1) append | ordered, index access O(1) |
| dict / set | O(1) avg | O(1) | hashing; no order guarantees pre-3.7 |
| heap | O(1) peek | O(log n) | priority queue |
| sorted list (bisect) | O(log n) | O(n) | keep sorted for range queries |

## Interview behaviour
1. Clarify input size, format, constraints **before** coding.
2. State data-structure choice and WHY first.
3. Call out edge cases: empty input, huge files, negatives, duplicates.
4. State time/space complexity unprompted.
