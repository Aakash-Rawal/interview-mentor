---
id: pe-cod-07
domain: pe
topic: coding
difficulty: easy
tags: [strings, parsing]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Parse `ps aux`-style output and print the top 3 processes by RSS, with their command name. Columns are whitespace-separated but the command field can contain spaces.

## What interviewers look for
- Spots the variable-column problem and solves it with maxsplit rather than a fragile regex
- Confirms which column is RSS and its units before trusting the number
- Skips the header and defends against short or weird rows instead of crashing
- Uses heapq.nlargest or a small heap and can say why it beats a full sort for k=3
- Notes what RSS actually means operationally (shared pages, not a memory budget)

## Strong answer covers
1. Skips the header line explicitly (first line, or detect a line starting with 'USER'), rather than letting int('RSS') raise
2. Uses `line.split(None, 10)` so the first 10 whitespace-separated fields are parsed and the command — which contains spaces and arbitrary arguments — stays intact as the final element; explains why plain `split()` breaks and why splitting from the right or regex is more brittle
3. Identifies the RSS column correctly for `ps aux` (field index 5, after USER PID %CPU %MEM VSZ) and states its unit — kilobytes — converting to MB for the output; mentions `ps -eo rss,comm --sort=-rss` as the shell answer that avoids parsing entirely
4. Top-3 via `heapq.nlargest(3, rows, key=lambda r: r.rss)` — O(n log 3) — and contrasts with sorting all rows O(n log n); at a few hundred processes either is fine, and says so rather than over-engineering
5. Defensive parsing: try/except on the int conversion, skip rows with fewer than the expected number of fields, count and report skipped rows; zombie/defunct processes and kernel threads in brackets have odd or zero fields
6. Edge cases: fewer than 3 processes, ties on RSS, empty input, a truncated last line if reading from a pipe, and `ps` output width truncation (`ps aux` may clip the command — `ps auxww` doesn't)
7. Reads from stdin/a file so it composes in a pipeline, streams line by line so it works for a huge saved snapshot, and exits non-zero with a message on unparseable input
8. Interprets the result: RSS counts shared pages per process so summing RSS double-counts; `/proc/<pid>/status` VmRSS, smaps_rollup or PSS is more accurate, and RSS is the right first signal for an OOM investigation

## Follow-ups
- Do this from /proc directly instead of shelling out to ps. What do you read and what races do you have to handle?
- The box is already OOMing and ps is slow to return. What's your approach then?
- Summing RSS across all processes gives more than total RAM. Explain.
- Make it a 10-second sampler that reports processes whose RSS grew the most over a minute.

## Sample answer
The trap here is the command field, which contains spaces, so a plain `split()` would scatter the arguments across fields and shift my indices. I'd use `split(None, 10)`: the first ten fields get parsed normally and everything after is one command string. I skip the header — either the first line or any line starting with USER — because otherwise int('RSS') blows up. For `ps aux` the RSS column is index 5 and it's in kilobytes, so I convert to MB for readability. I parse into small tuples and take `heapq.nlargest(3, rows, key=...)`, which is O(n log 3); a sort would work too at a few hundred processes, but the heap is the habit I want for large inputs. Defensively: try/except around the int conversion, skip rows that are too short, count the skips and report them — zombies and kernel threads produce odd lines. I read from stdin so it pipes. Two things worth saying out loud: `ps auxww` avoids command truncation, and RSS includes shared pages, so summing it double-counts; for real accounting I'd read VmRSS or smaps_rollup PSS from /proc. Honestly, `ps -eo rss,comm --sort=-rss | head -4` is the answer if parsing isn't the point.
