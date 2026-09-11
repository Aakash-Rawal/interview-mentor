---
id: ne-fun-06
domain: ne
topic: networking_fundamentals
difficulty: medium
tags: [dns, resolution]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Explain how DNS resolution works end to end, then: what happens to your service when the authoritative nameservers become unreachable, and how long until users notice?

## What interviewers look for
- Distinguishes recursive from authoritative cleanly and doesn't muddle who caches what
- Answers 'how long until users notice' with a TTL-based reasoning chain, not a guess
- Treats TTL as an explicit availability-versus-agility trade-off with numbers
- Mentions that failure is gradual and staggered, not a cliff, and what that does to the incident signal
- Brings in practical mitigations: anycast, diverse providers, SOA/negative TTL

## Strong answer covers
1. Resolution path: stub resolver → recursive resolver (which has its own cache) → root → TLD (.com) → authoritative; the recursive does the walking, the stub just asks once
2. Record types named and used correctly: A/AAAA, CNAME, NS, SOA, MX, TXT, PTR, SRV; delegation via NS records and glue
3. Caching by TTL at the recursive resolver, plus stub/OS and browser caches with their own shorter behaviour
4. If all authoritatives are unreachable: cached answers keep serving until TTL expiry, then resolvers return SERVFAIL — so the outage arrives gradually, staggered per resolver and per record, over roughly one TTL
5. Negative caching governed by the SOA minimum field — an NXDOMAIN mistake sticks around independently of the record TTL
6. TTL trade-off with numbers: 300s means fast failover/migration but no resilience to an authoritative outage and more query load; 86400s means users keep working through a long outage but a planned cutover takes a day
7. Also: NS record TTLs and TLD delegation TTLs matter — resolvers may retain delegation long enough to keep retrying dead servers
8. Mitigations: anycast authoritative, two independent DNS providers with separate NS sets, health-checked failover, serve-stale (RFC 8767) on resolvers, and pre-lowering TTLs before planned migrations
9. Tools: `dig +trace` to walk the delegation, `dig @ns1.example.com example.com` to query an authoritative directly and bypass cache, `dig +norecurse` against a resolver to see what's cached and the remaining TTL

## Follow-ups
- You need to migrate a service IP next week. What's your TTL plan and timeline either side of the cutover?
- Users in one region report failures and others don't, with the same TTL everywhere. What explains that?
- How does serve-stale change your answer, and can you rely on it?
- Your monitoring queries the authoritative directly and stays green while users fail. How would you rebuild the check?

## Sample answer
The stub resolver on the host asks its configured recursive resolver. If that resolver has nothing cached, it walks the tree: root servers give it the .com NS records, the TLD gives it the delegation for example.com, and the authoritative server returns the A or AAAA. Everything along the way gets cached at the recursive for the record's TTL, and stubs and browsers cache too. Now, if my authoritatives all go dark, nothing breaks immediately. Every resolver that already has the answer keeps serving it until that TTL expires, then it tries to refresh, fails, and returns SERVFAIL. So the outage arrives gradually over roughly one TTL, staggered by when each resolver last fetched — which is horrible for the incident signal because it looks like a slow trickle of complaints rather than a clean cliff. With a 300-second TTL, users notice within five minutes; with a day-long TTL, most people keep working all day. That's the trade-off: short TTLs buy you fast failover and migration agility, long TTLs buy you resilience to exactly this failure. My mitigations are anycast authoritatives across two independent providers with separate NS sets, and pre-lowering TTLs before planned cutovers. For debugging I'd use `dig +trace` to walk the delegation and `dig @ns1` to bypass cache and hit the authoritative directly.
