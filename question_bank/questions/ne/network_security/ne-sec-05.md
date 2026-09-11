---
id: ne-sec-05
domain: ne
topic: network_security
difficulty: medium
tags: [bgp, rpki, hijack, detection]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
How would you detect and respond to someone hijacking one of your prefixes on the internet, and what stops it from working in the first place?

## What interviewers look for
- Distinguishes detection sources you control from external ones and knows the internal symptom is a traffic cliff
- Knows the practical response levers and their limits — more-specifics only work down to /24 in the DFZ
- Treats upstream/peer phone calls and NOC escalation as a real, planned part of the response
- Explains RPKI honestly: what ROV blocks, what it doesn't, and who has to deploy it for it to help
- Mentions leaks and route-object hygiene, not just origin hijacks

## Strong answer covers
1. Detection: external route monitoring — RIPE RIS/RIPEstat, BGPalerter, BGPmon/Cloudflare Radar or a commercial feed — alerting on unexpected origin AS, new more-specifics of your space, and unexpected upstream AS-paths; plus internal signals (sudden traffic drop on the prefix, one-way flows, latency/geo anomalies, customer reports)
2. Confirm before acting: look up the prefix in multiple looking glasses and route collectors to see how widely the bogus announcement propagated and which AS is originating/propagating it — distinguish a hijack from a leak (your own prefix re-advertised via the wrong path) and from a fat-finger by a customer
3. Response levers: announce more-specifics (a /24 pair covering a hijacked /23, since most operators filter longer than /24 in the DFZ), so you can't out-specific someone who already hijacked your /24
4. Escalation: call your transit providers' NOCs with a pre-prepared LOA/contact list, use PeeringDB and NOC contacts for the offending AS and its upstreams to get the announcement filtered or withdrawn, and post to relevant operator mailing lists/NSP-SEC; expect hours, not minutes
5. Prevention on your side: publish RPKI ROAs for every prefix with the correct maxLength (don't over-permit maxLength or you enable more-specific hijacks), keep IRR route/route6 and as-set objects accurate, and run ROV at your own edge so you drop invalids inbound
6. Prevention that depends on others: your transit providers must do strict prefix-list filtering and RPKI-based drop (MANRS conformance is the thing to demand in contracts); a hijack only fails if upstreams filter it
7. Session-level hygiene that stops a different attack class: prefix-lists in and out on every eBGP session, max-prefix limits with restart timers, bogon and default-route filters, GTSM/TTL security, MD5 or TCP-AO, and disabling unused address families
8. Limits to state honestly: RPKI ROV validates origin only — it doesn't stop AS-path forgery where the attacker prepends your ASN, doesn't stop route leaks (ASPA and RFC 9234 roles/OTC are the emerging answers), and doesn't help if a large network ignores invalids; also encrypt sensitive traffic so a hijack yields ciphertext, and monitor certificate issuance since BGP hijacks are used to fraudulently obtain domain-validated certs

## Follow-ups
- Your ROA has maxLength /24 on a /20 you only ever announce as a /20. Why is that dangerous?
- Traffic is going somewhere unexpected but the AS-path shows your own ASN as origin. What kind of attack is this and does RPKI catch it?
- How would you tell a hijack apart from a route leak by an accident-prone customer, and does the response differ?
- What would you put in the contract or peering policy with a new transit provider to reduce this risk?

## Sample answer
Detection comes from two directions. Externally, I want route monitoring — BGPalerter or RIS-based alerting — firing on any origin AS that isn't mine for my space, on new more-specifics, and on unexpected AS-paths. Internally, the symptom is a traffic cliff on that prefix plus one-way flows and customer reports. First I confirm on public looking glasses and collectors: who is originating it, how far has it propagated, and is this actually a hijack or a leak of my own routes via a wrong path. Response: if they hijacked a /23 I announce the two covering /24s, since more-specifics win — but I say the limit up front, most of the DFZ filters longer than /24, so if my /24 was hijacked I can't out-specific them and I'm entirely dependent on getting the announcement filtered. So the real lever is phone calls: my transit NOCs with an LOA ready, then the offending AS and its upstreams via PeeringDB, plus operator mailing lists. Prevention: publish ROAs with a tight maxLength — don't set /24 on a /20 you never deaggregate, that just authorises the attacker — keep IRR objects accurate, run ROV at my edge, and require MANRS-style filtering from providers. And I'd be honest that ROV only validates origin: path forgery and leaks need ASPA, and encrypting traffic means a hijack yields ciphertext.
