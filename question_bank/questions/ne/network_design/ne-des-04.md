---
id: ne-des-04
domain: ne
topic: network_design
difficulty: hard
tags: [bgp, internet-edge, traffic-engineering, peering]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design the internet edge for a company with two datacenters and three transit providers. Cover inbound traffic engineering and failure modes.

## What interviewers look for
- Separates outbound control (deterministic, LOCAL_PREF) from inbound control (approximate, influence-only) and says so
- Counts backhaul capacity for the site-isolation case rather than just saying 'iBGP between sites'
- Lists concrete BGP hygiene knobs, not just 'filtering'
- Walks at least two failure modes end to end with traffic consequences
- Mentions DDoS and control-plane protection as part of edge design

## Strong answer covers
1. Physical/logical layout: two edge routers per site, each provider on a different router where possible, diverse entrances/cross-connects; IXP peering alongside transit for cheap direct paths; full tables vs default-only decision per router capability
2. Outbound policy: LOCAL_PREF to prefer peering > cheap transit > expensive transit, with communities set on ingress for readability; MED/AS-path only as tiebreakers; ECMP or per-prefix balancing between equal transits
3. Inbound TE: AS-path prepending, provider-specific communities to influence their LOCAL_PREF, selective more-specific announcements per site, and the honest caveat that inbound is approximate and driven by other people's policy
4. Prefix strategy: announce the aggregate from both sites plus site-specific more-specifics so either site can absorb all traffic if the other's more-specific disappears
5. Protections: max-prefix limits per session, inbound and outbound prefix-lists/AS-path filters, RPKI ROV with invalid-drop, bogon and private-ASN filtering, BFD on eBGP where supported, GTSM/TTL security, MD5 or TCP-AO, CoPP for the control plane, and a no-transit policy for peers
6. iBGP design: iBGP between the two sites (or via route reflectors) so a site that loses all transit still has a path, plus next-hop-self and consistent IGP for loopback reachability
7. Site-isolation failure walk: site A loses all three transits → all of A's inbound must arrive via B and cross the backhaul; size and measure that backhaul, and decide whether to withdraw A's more-specifics or shift DNS/global LB weights instead
8. DDoS response: upstream scrubbing, RTBH community to providers, flowspec where supported, and pre-agreed provider escalation paths

## Follow-ups
- One transit leaks you a full table plus 400k bogus prefixes at 3 a.m. What fires first, and what's your recovery sequence?
- You prepend three times to one provider and traffic barely moves. Why, and what would you try next?
- How do you decide whether an edge router takes full tables or a default route, and what breaks with each choice?
- Someone hijacks a more-specific of your prefix. Walk me through detection and response.

## Sample answer
Two edge routers per site, each with eBGP to its own transit provider so no single box or provider is a shared fate, plus IXP peering for the cheap direct paths. Outbound I control precisely with LOCAL_PREF: peering highest, then cheap transit, then the expensive one, and I set those with communities tagged at ingress so policy is readable. Inbound I only influence: prepending, provider communities that nudge their LOCAL_PREF, and per-site more-specifics. I say up front that inbound is approximate because it's decided by other people's policy. Announcement plan: both sites announce the aggregate, each also announces its own more-specific, so if one site dies the aggregate from the other still pulls the traffic. Hygiene: max-prefix per session, prefix-lists and AS-path filters in both directions, RPKI ROV dropping invalids, bogon filters, BFD, TTL security, MD5, and CoPP. iBGP between the sites with next-hop-self so a site that loses all three transits still has a path — but the real question is whether the backhaul can carry that site's full inbound load. If it can't, I'd rather withdraw the more-specifics and let DNS or the global LB move the traffic. For DDoS: upstream scrubbing, an RTBH community with each provider, flowspec where they support it.
