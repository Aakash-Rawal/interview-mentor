---
id: pe-cod-01
domain: pe
topic: coding
difficulty: easy
tags: [file-io, streaming]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
You have a multi-GB web server log. Each line has a numeric response-time field. Compute the average response time. The file does not fit in memory.

## What interviewers look for
- Asks about file size, line format, field position and delimiter before writing anything
- Reaches for line-by-line iteration instinctively rather than read()/readlines()
- Treats malformed lines as normal traffic: counts them, keeps going, reports at the end
- States complexity unprompted — O(n) over lines, O(1) memory — and names what n is
- Handles the zero-count case before the interviewer has to ask

## Strong answer covers
1. Streams the file with `for line in f` (constant memory); explicitly rejects `f.read()`/`f.readlines()` on a multi-GB file and says why
2. Keeps only two accumulators: running `total` (float) and `count` (int); average = total/count at the end, no list of values retained
3. Parses defensively: `line.rstrip('\n').split()`, checks `len(parts) > idx`, wraps the numeric conversion in try/except ValueError, increments a `skipped` counter and logs a sample line rather than crashing
4. Confirms which field index holds response time and how to validate it — e.g. eyeball `head -5`, or key off a named field / regex / CSV or JSON parser instead of a positional index if the format allows
5. Empty file or all-malformed input: returns None or 0 explicitly instead of raising ZeroDivisionError
6. States complexity: O(n) time in number of lines, O(1) memory; I/O-bound so throughput is limited by disk, not CPU
7. Mentions open() with `encoding='utf-8', errors='replace'` so a single bad byte doesn't kill a 40 GB job
8. Reports the skipped-line count alongside the answer so the number is trustworthy

## Follow-ups
- Now give me p99 of the same field instead of the average — what changes, and what's your memory story?
- The log is gzipped and arrives as 200 files per hour. How do you parallelise this and still get one correct average?
- How would you compute average per HTTP status code, and what bounds your memory then?
- Your average looks suspiciously low compared to the dashboard. How do you debug your parser versus the data?

## Sample answer
First, two questions: what's the exact line format and which field is the response time, and is it always numeric? I'll assume whitespace-separated and field index 9 — I'd check with `head` first, and if it's structured JSON I'd parse properly rather than by position. Since it doesn't fit in memory I stream: open with utf-8 and errors='replace', iterate `for line in f`, split, and if the line is short or the field won't convert to float, increment a skipped counter and continue — I don't want one bad line to kill a forty-minute job. I keep only a running total and count, so memory is O(1) regardless of file size; time is O(n) in lines and it's I/O-bound. At the end, if count is zero — empty file, or everything malformed — I return None rather than dividing by zero, and I print the skipped count so the caller knows how much I dropped. If they later want p99 I can't do it with two scalars: I'd either keep all values, sort on disk, or use a sketch like t-digest or HdrHistogram with bounded memory.
