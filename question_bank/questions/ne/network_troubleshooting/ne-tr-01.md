---
id: ne-tr-01
domain: ne
topic: network_troubleshooting
difficulty: hard
tags: [latency, mtr, methodology]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Users in one region report intermittent high latency to your service; other regions are fine. Diagnose it.

## What interviewers look for
- Pins down the failure before testing: which source prefixes, which destination VIP, since when, latency magnitude, and whether it correlates with time of day
- Insists on bidirectional measurement rather than trusting a single client-side traceroute
- Separates ICMP artefacts from real user-visible loss instead of blaming the first hop that shows red
- Correlates the measurement window with control-plane and capacity events rather than guessing
- Proposes a mitigation with a known blast radius (shift traffic/prepend/depref) while root cause continues

## Strong answer covers
1. Defines failure precisely: affected source ASNs/prefixes, destination IP/port, onset time, intermittent vs constant, magnitude (e.g. p50 40ms → p99 400ms) and whether TCP retransmits accompany it
2. Runs mtr/traceroute from both directions — from an affected client toward the service AND from a service-side host or looking-glass back toward the client prefix — because forward and return paths differ
3. Uses long runs (`mtr -c 500`, or `mtr --tcp -P 443` to avoid ICMP-only paths) and compares per-hop loss/latency distributions, not a single sample
4. Correctly interprets intermediate-hop loss/latency that does not persist to the final hop as ICMP rate-limiting/deprioritisation on the router control plane, not real forwarding loss; only loss that carries through to the last hop counts
5. Checks control-plane changes in the window: BGP session flaps and route changes (`show bgp neighbor` flap counters, route-change/BMP logs), new or withdrawn peer, transit failover moving the region onto a congested path, prefix change on either side
6. Checks for asymmetric routing and ECMP polarisation: vary source port / use paris-traceroute to see if only a subset of flows hit the bad path; a single bad ECMP member produces intermittent symptoms for a subset of users
7. Checks peering/transit congestion evidence: link utilisation and output drops on egress ports at the relevant exchange/transit port, diurnal pattern, microbursts with low average utilisation
8. Mitigation and prevention: shift the region's traffic to another transit/peer (AS-path prepend, MED, local-pref, anycast withdrawal), then fix; prevention is per-region synthetic probes, per-peer latency/loss dashboards, drop/queue alerting and capacity thresholds

## Follow-ups
- The bad hop is inside a transit provider's network and you can't log into it. What evidence do you assemble for the ticket, and what do you do meanwhile?
- Latency is elevated but there is zero loss anywhere. What besides congestion produces that, and how would you test each?
- Your only anycast node for that region is the one showing latency. How do you decide between withdrawing the announcement and riding it out?
- How would you have detected this before users did, and what would the alert threshold be so it doesn't page on ICMP noise?

## Sample answer
First I scope it: which client prefixes, to which VIP and port, since when, how bad — is it p99 only or everyone, and are TCP retransmits or just latency? Then I measure both directions, because the forward and return paths are different. mtr from an affected client to the VIP, and mtr or a looking glass from the service side back into that client prefix, long runs, 500 packets, and TCP mode if ICMP is filtered. I read the per-hop columns carefully: loss at hop 6 that disappears by hop 10 is ICMP deprioritisation on that router's control plane, not real loss. Only loss and latency that persists to the final hop is real. In parallel I ask what changed — BGP flap counters and route-change logs for that window, a peer that went down and pushed the region onto transit, or a congested exchange port with output drops at peak. If it's a subset of flows, I vary source port to test ECMP polarisation. If users are hurting I mitigate first: prepend or lower local-pref so that region egresses via another path, verify with the same mtr, then chase root cause. Prevention: synthetic probes per region and per-peer loss dashboards.
