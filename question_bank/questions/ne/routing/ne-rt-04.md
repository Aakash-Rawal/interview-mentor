---
id: ne-rt-04
domain: ne
topic: routing
difficulty: hard
tags: [bgp, route-leak, policy, incident]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A junior engineer adds a prefix-list change on an edge router and suddenly your network is transiting traffic between two upstream providers. What happened, how do you stop it, and how do you make it impossible to repeat?

## What interviewers look for
- Stops the bleeding before doing forensics — incident instinct
- Quantifies blast radius: which prefixes leaked, to whom, how much traffic arrived
- Distinguishes the immediate fix, the correct fix, and the systemic prevention
- Treats the root cause as a policy-architecture defect (permit-by-default) not as 'a junior made a typo'
- Mentions external coordination — the upstreams, and what they should have been doing

## Strong answer covers
1. Diagnosis: prefixes learned from upstream A are being re-advertised to upstream B, so you're announcing paths you have no business announcing and both providers are steering transit traffic through you
2. Immediate containment: roll back the change (or apply a deny-all export filter on the eBGP sessions to both upstreams), then soft-clear outbound / route-refresh; verify with `show ip bgp neighbor <peer> advertised-routes` and prefix counts before/after
3. Symptom confirmation: interface utilisation spike on the transit links, advertised-prefix count jumping from your ~tens of prefixes to hundreds of thousands, upstream max-prefix alarms, possibly your own session being shut down by the upstream
4. Root cause class: the export policy was permit-by-default, so removing or reordering an entry in the prefix-list exposed the full table rather than failing closed
5. Structural prevention: default-deny export policy with an explicit final deny, and only explicitly-tagged prefixes permitted out
6. Community tagging by source (customer / peer / transit) applied on ingress, with export policy matching only the customer/originated communities; no-export where appropriate
7. Outbound max-prefix or prefix-count limits (many platforms support outbound limits) and inbound max-prefix on the upstreams' side; alerting on advertised-prefix delta
8. RPKI ROV and IRR-based prefix filters, plus BGP role / ASPA-style leak prevention (RFC 9234) where supported, and the fact that a well-run upstream would have filtered this for you
9. Process prevention: peer-review of policy changes, lab or dry-run validation of the generated config, config generated from a source of truth rather than hand-edited, staged rollout with a commit-confirmed / automatic rollback timer

## Follow-ups
- Your upstream didn't filter you either. What would you say to them, and what would you ask for in the peering agreement?
- Write the outline of the export policy you'd want — what matches, in what order, and what's the last line?
- How do you detect this within 60 seconds next time, from your own telemetry and from external sources?
- Suppose the leak had been more-specifics of someone else's space rather than transit routes. How does the response differ?

## Sample answer
That's a route leak: prefixes learned from one transit are being re-advertised to the other, so both of them now think we're a valid path and are pouring traffic through us. First job is stopping the bleeding, not forensics. I roll back the change, or if that's ambiguous I drop a deny-all export policy onto both upstream sessions and route-refresh outbound. Then verify with `show ip bgp neighbor advertised-routes` — I should be back to our own tens of prefixes, not hundreds of thousands — and watch the transit link utilisation drop. Then the real root cause. This isn't 'a junior made a mistake'; it's that our export policy was permit-by-default, so deleting one prefix-list line exposed the whole table instead of failing closed. The fix is default-deny export with an explicit terminal deny, ingress community tagging by source — customer, peer, transit — and export policy that only permits the customer and originated communities. On top of that: outbound prefix-count limits with alerting on a sudden delta, RPKI ROV and IRR filters, and BGP roles for leak prevention where the platform supports it. Process-wise, policy changes get generated from source of truth, peer-reviewed, and committed with a confirm timer so an unreviewed change auto-reverts. And I'd note our upstream should have been filtering us too.
