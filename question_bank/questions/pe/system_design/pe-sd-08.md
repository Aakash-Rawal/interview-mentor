---
id: pe-sd-08
domain: pe
topic: system_design
difficulty: easy
tags: [url-shortener, id-generation, caching, estimation]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design a URL shortener. Focus on the ID generation scheme and how you'd scale reads.

## What interviewers look for
- Gathers requirements and does arithmetic before choosing a design — read/write ratio, key length, storage growth
- Compares at least two ID schemes concretely rather than asserting one, including collision and enumeration implications
- Recognises the mapping is immutable, and uses that to make caching trivially easy
- Names the 301 vs 302 trade-off as a product decision (analytics and revocation vs traffic reduction), not a detail
- Keeps the redirect path short and pushes everything optional — analytics, abuse scanning — off it asynchronously

## Strong answer covers
1. Requirements pinned down: create QPS vs redirect QPS (e.g. 100M new links/month ≈ 40 writes/s; reads 100x that ≈ 4k QPS avg, ~15k peak), custom aliases, expiry/deletion, analytics granularity, latency target (p99 redirect < 50 ms), availability target
2. Key space arithmetic: 62^7 ≈ 3.5×10^12 with 7 base62 chars — plenty for 10^10 links; shows the length choice is derived, not assumed
3. Storage estimate: ~500 bytes per row × 100M/month ≈ 50 GB/month, under 1 TB/year — fits a single KV store or a small sharded Postgres, so no need to over-shard early
4. ID scheme comparison: (a) counter + base62 — dense, no collisions, but sequential/enumerable and needs a central counter, mitigated by each host leasing blocks of e.g. 64k IDs from a DB/ZooKeeper, with gaps on restart being fine; (b) random 7-char with conditional put-if-absent — non-enumerable, collision retry rate stays negligible until the space is heavily filled; (c) hash of the URL — gives dedupe but needs truncation/collision handling
5. Read path: cache-aside Redis or an in-process LRU plus CDN; mapping is immutable so TTLs can be long or infinite and invalidation is only needed on delete/expiry; Zipf distribution means a modest cache gets >90% hit rate; single-flight or request coalescing against stampede on a cold cache
6. 301 vs 302: 301 is cached by browsers and intermediaries so it cuts traffic but destroys per-click analytics and makes revocation impossible; 302/307 keeps every hit on your servers. Picks one and says why; may use short-TTL caching headers as a middle ground
7. Analytics off the hot path: fire-and-forget to a queue/log or local buffer, batch aggregate, accept at-least-once and approximate counts; the redirect must not block on the counter store
8. Failure modes and abuse: DB down → serve reads from cache and reject creates (degrade to read-only); rate-limit creation per account/IP; malware/phishing blocklist checked async with retroactive disable; reserved-word namespace for custom aliases with a conditional insert for uniqueness

## Follow-ups
- You want redirects served from five regions but writes from one. What does the read path look like, and what does a user see right after they create a link?
- Someone is scraping your key space to enumerate links. How would you detect it, and what would you change in the design?
- You now need per-link click counts accurate to within 1% at 50k redirects/s. What do you build, and where would you accept approximation?
- Links have a TTL and 30% expire within a year. How do you expire and reclaim them without a giant scan?

## Sample answer
Let me size it first. Say 100 million new links a month — that's about 40 creates a second, trivial — and a 100:1 read ratio, so roughly 4,000 redirects a second average, call it 15,000 at peak. Rows are a few hundred bytes, so under a terabyte a year: this fits one well-behaved datastore, and I'd resist sharding until it doesn't. Seven base62 characters gives 3.5 trillion keys, which is comfortable. For ID generation I'd compare two. A counter encoded to base62 is dense and collision-free, but sequential keys are enumerable and a single counter is a bottleneck — I'd fix that by having each host lease blocks of 64k IDs, and just accept gaps when a host dies. The alternative is a random seven-character key inserted with a put-if-absent; collisions are negligible at these volumes and it's not enumerable. I'd take the random one for that reason. Reads are the easy part because the mapping is immutable: cache-aside with effectively unbounded TTLs, invalidate only on delete, and the click distribution is Zipfian so a small cache carries most traffic. I'd use 302 rather than 301 so I keep analytics and the ability to revoke a link, and I'd push click logging onto a queue so the redirect path is a cache lookup and a header write, nothing else.
