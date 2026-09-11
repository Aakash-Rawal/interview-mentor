---
id: pe-cod-06
domain: pe
topic: coding
difficulty: hard
tags: [dedup, hashing, memory]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Two log files, each 50 GB, on a machine with 8 GB RAM. Output the lines present in both files.

## What interviewers look for
- Immediately rules out the naive set-of-one-file approach with a memory estimate, not just a hunch
- Offers at least two of external sort/merge, hash partitioning, and Bloom filter, and compares I/O cost
- Understands the key property of hash partitioning: equal lines hash to the same bucket
- Knows Bloom filters have false positives but no false negatives, and therefore require a verification pass
- Reasons in passes over 100 GB and converts that to wall-clock on real disk bandwidth

## Strong answer covers
1. Rejects `set(open(f1))` with arithmetic: 50 GB of line data plus Python string and set overhead is several times RAM; even deduplicated it's far past 8 GB
2. Hash-partition approach: single streaming pass over each file writing lines to one of k buckets by `hash(line) % k` (k chosen so each bucket is comfortably under a few GB, e.g. k=64 gives ~800 MB per side); identical lines always land in the same bucket index, so intersect bucket i of A with bucket i of B independently, holding only one bucket's set in RAM
3. External sort/merge approach: `sort` each file (GNU sort spills to disk, honours `-S` and `-T`), then `comm -12 a.sorted b.sorted` or a linear two-pointer merge — O(n log n) I/O but no hash assumptions and streams the output
4. Bloom filter approach: build a Bloom filter over file A's lines in a fixed few hundred MB, stream B against it to get candidates, then verify candidates exactly (because false positives are possible, false negatives are not) with a second pass or an exact set over the much smaller candidate set
5. Quantifies I/O: hash partitioning is roughly 2 reads + 1 write + 1 read per side (~4 passes over 100 GB); on a disk sustaining 200 MB/s that's tens of minutes, so the job is I/O-bound and disk bandwidth and free scratch space are the real constraints
6. Handles duplicates and semantics explicitly: does 'present in both' mean distinct lines, or preserve multiplicity? Dedup within a bucket with a set, or count occurrences if multiplicity matters
7. Practical details: hash on the normalised line (strip trailing newline, decide on trailing whitespace/encoding), `PYTHONHASHSEED`/`hash()` is randomised per process so use a stable hash like md5/xxhash if partitioning across runs or machines; batch writes to bucket files to avoid tiny-write overhead and watch the open-file-descriptor count
8. Mentions the obvious shortcuts if applicable: if one file is much smaller or a key field rather than whole lines is the join key, the problem gets much cheaper; and if the data is already sorted, it's a single streaming merge

## Follow-ups
- Only 2 GB of scratch disk is free. Now what?
- You have 10 machines instead of one. How does your plan change and where's the bottleneck?
- Your hash partitioning produces one 6 GB bucket and 63 tiny ones. What happened and how do you recover?
- Size the Bloom filter for 500 million distinct lines and a 1% false positive rate, and justify the verification pass.

## Sample answer
The naive answer — load file A into a set and stream B — needs way more than 8 GB, since 50 GB of raw lines becomes multiples of that as Python strings. So I need to divide the problem. My default is hash partitioning: stream each file once, and for each line write it to bucket `stable_hash(line) % 64` on disk. The key property is that identical lines always land in the same bucket number on both sides, so I only ever need to compare bucket i of A with bucket i of B. Each bucket is around 800 MB, so I load A's bucket into a set, stream B's bucket against it, and emit matches — one bucket resident at a time. That's about four passes over 100 GB; at a couple hundred MB/s I'm I/O-bound in the tens of minutes, and I need 100 GB of scratch. The alternative is external sort both files with `sort -S` and `comm -12`, which streams and needs no hash but costs n log n I/O. A Bloom filter over A lets me shrink B to candidates in fixed memory, but it has false positives, so I must verify exactly afterwards. I'd also pin down whether duplicates matter and use a stable hash, not Python's randomised `hash()`.
