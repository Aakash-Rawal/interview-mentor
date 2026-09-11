---
id: ne-rt-02
domain: ne
topic: routing
difficulty: medium
tags: [bgp, path-selection, troubleshooting, policy]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
You have two paths to the same prefix and traffic is taking the one with the longer AS path. How do you find out why BGP chose it?

## What interviewers look for
- Recites the path-selection order correctly and in order, without being prompted
- Reasons from evidence — reads the actual best-path output rather than guessing
- Suspects policy (inbound route-map setting local-pref) before suspecting protocol bugs
- Distinguishes 'this is the intended design' from 'this is a misconfiguration' before changing anything
- Has a safe change plan: soft-clear, verify, rollback

## Strong answer covers
1. Full selection order: highest weight (Cisco-local, not advertised), highest LOCAL_PREF, locally originated, shortest AS_PATH, lowest ORIGIN (IGP < EGP < incomplete), lowest MED, eBGP over iBGP, lowest IGP metric to next-hop, then oldest path / lowest router-ID / lowest neighbour address
2. Explicitly flags that LOCAL_PREF is evaluated before AS_PATH, so a higher local-pref legitimately beats a shorter AS path — the most likely cause here
3. Uses `show ip bgp <prefix>` / `show route protocol bgp <prefix> detail` to see all candidate paths and the 'best path' reason line the platform prints
4. Inspects the inbound route-map / policy-statement on the session that won: `show route-map`, `show ip bgp neighbor <x> received-routes` versus `routes` to compare pre- and post-policy
5. Considers weight as a hidden local override that is not visible on other routers and not advertised anywhere
6. Checks AS_PATH prepending counts, and whether the longer path is actually longer after confederation/AS_SET counting rules
7. Also checks for MED comparison (only between paths from the same neighbouring AS unless always-compare-med) and a lower IGP metric to next-hop as tie-breakers further down
8. Change hygiene: fix the policy, use a soft clear (`clear ip bgp <peer> soft in` / route-refresh) rather than a hard reset, confirm with the same show command, keep a rollback

## Follow-ups
- The route-map looks correct and local-pref is equal on both. What's next down the list, and how would you prove it?
- The shorter AS path is actually a path you don't want to use — how would you make the longer one preferred, cleanly and documentably?
- How would you make this diagnosable at 3 a.m. by someone who didn't build the policy — what tagging or tooling would you add?
- Same symptom but the two paths are on different routers in your AS, and the losing router isn't even advertising its path to the RR. Why?

## Sample answer
I walk the selection order out loud and test each step against the actual output. Weight first — Cisco-local, never advertised, so it can be an invisible override on this one box. Then local preference, and that's my prime suspect, because local-pref is evaluated before AS path length. Then locally originated, AS path length, origin code, MED, eBGP over iBGP, IGP metric to the next hop, then the age and router-ID tie-breakers. Concretely I run `show ip bgp <prefix>` and look at all the candidate paths plus the best-path reason the platform prints — most vendors will literally tell you 'best, local pref'. If local-pref differs I go look at the inbound route-map on that session, and I compare `received-routes` against `routes` to see what policy did to the attributes on the way in. Nine times out of ten someone set local-pref 200 on a transit session for a maintenance and never removed it. Before I change anything I ask whether that's actually intended — a longer AS path can be the cheaper or better-performing exit. If it's wrong, I fix the policy, do a soft clear with route refresh rather than bouncing the session, and re-verify with the same command.
