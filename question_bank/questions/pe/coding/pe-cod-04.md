---
id: pe-cod-04
domain: pe
topic: coding
difficulty: medium
tags: [parsing, intervals]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Given a list of on-call shifts as (start, end) timestamps, possibly overlapping, return the merged set of covered intervals and any gaps in coverage over a given window.

## What interviewers look for
- Sorts by start and sweeps, rather than doing pairwise overlap checks
- Nails the half-open versus closed interval question with the interviewer before coding
- Derives gaps as the complement of merged coverage within the window, including leading and trailing gaps
- Enumerates edge cases without prompting: touching intervals, shifts entirely outside the window, clipping, empty input
- States O(n log n) dominated by the sort and O(n) space

## Strong answer covers
1. Sort intervals by start time, then linear sweep: if `cur_end >= next_start` extend `cur_end = max(cur_end, next_end)`, else emit and start a new interval — O(n log n) time, O(n) output space
2. Clarifies interval semantics up front: are ends inclusive or half-open, and do touching shifts ([9,10] and [10,11]) merge? For contiguous coverage they should
3. Clips input to the query window first (or during the sweep) and drops shifts that fall entirely outside it, so gaps are computed relative to the requested window
4. Gap computation: walk merged intervals; gap from window_start to first merged start, between consecutive merged intervals, and from last merged end to window_end; a gap only counts if its length is > 0
5. Empty input (or no shift overlapping the window) yields one gap covering the whole window — not an empty result or a crash
6. Handles zero-length or inverted intervals (end < start) by validating and rejecting/logging rather than producing nonsense
7. Mentions timezone/DST and unit hygiene: normalise everything to epoch seconds or UTC before comparing, since shift schedules are a classic DST bug source
8. Notes the operational use: this is exactly how you audit an on-call rotation for uncovered minutes, and the same sweep computes max concurrent coverage (double-booking) with a +1/-1 event sweep

## Follow-ups
- Also report where two or more people are on call simultaneously. How does your sweep change?
- There are 10 million shift records and you need this per team, per week. How do you make it fast?
- How do you handle shifts that wrap midnight in local time across a DST boundary?
- You need to alert when a gap is about to appear in the next 24 hours. How do you structure that job?

## Sample answer
First I'd pin down semantics: are the intervals half-open, and does a shift ending at 10:00 followed by one starting at 10:00 count as continuous? I'll assume half-open and that touching shifts merge. Everything gets normalised to epoch seconds up front — mixing local times across a DST change is how these audits go wrong. Then: filter to shifts overlapping the window and clip them to it, sort by start, and sweep. I hold a current interval; if the next start is at or before my current end, I extend the end to the max of the two; otherwise I emit the current one and start fresh. That's O(n log n) for the sort, O(n) for the sweep. Gaps are the complement: from window start to the first merged start, between each pair of merged intervals, and from the last merged end to window end, keeping only positive-length gaps. Edge cases: empty input means the whole window is one gap; shifts wholly outside the window are dropped; end-before-start records get logged and rejected. If they also want double-booking, I'd switch to a +1/-1 event sweep and track the running count, which gives merged coverage and concurrency from the same pass.
