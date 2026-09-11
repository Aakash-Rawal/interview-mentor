---
id: ne-sec-02
domain: ne
topic: network_security
difficulty: hard
tags: [ddos, bgp, edge, incident-response]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Your public API is under a volumetric DDoS that is saturating your transit links. What do you do in the first 10 minutes, and how do you architect to absorb the next one?

## What interviewers look for
- Separates the first-10-minutes triage from the architectural fix and doesn't blur them
- Classifies the attack (volumetric vs protocol vs application) from data before picking a control
- Knows that once transit is saturated the fix must happen upstream — your own edge is already the bottleneck
- States trade-offs honestly, especially that RTBH sacrifices the victim IP to save everything else
- Thinks about the control plane and the humans: CoPP, runbooks, pre-arranged provider contacts, comms

## Strong answer covers
1. Triage in minutes 0-3: confirm it's an attack not a launch/regression — interface utilisation and drops on transit, NetFlow/sFlow top talkers, packet size and pps vs bps, src distribution, protocol/port mix; check whether it's spoofed UDP reflection (DNS/NTP/memcached/CLDAP amplification) versus real TCP
2. Classification drives the control: volumetric (link saturation — must be handled upstream), protocol/state exhaustion (SYN flood — SYN cookies, conntrack limits, firewall session table), application L7 (HTTP floods — WAF, rate limit per IP/JA3, CAPTCHA, caching)
3. Engage upstream immediately: call transit providers/scrubbing provider on pre-arranged contacts, divert via GRE/BGP into scrubbing, request their filters; you cannot filter a full pipe at your own router
4. RTBH: announce the victim /32 with the provider's blackhole community (e.g. 65535:666) to drop it in their network — explicitly say this sacrifices that IP to save the link and everything else behind it; use only when the target is a single non-critical VIP
5. BGP flowspec where the provider supports it — surgical drop/rate-limit by src/dst/proto/port/packet-length instead of dropping the whole destination; plus local edge ACLs, uRPF, and per-source rate limits
6. Protect the control plane and stateful boxes: CoPP so BGP/SSH survive, keep the firewall/LB state table from exhausting, SYN cookies on the front end, don't let logging or NAT tables be the collapse point
7. Architecture: anycast the service across multiple POPs to split the attack, always-on CDN/scrubbing in front of the origin with the origin IPs hidden and locked to CDN ranges, over-provisioned or diverse transit with IXP capacity, autoscaling L7 tier, and separate management/OOB path
8. Operational readiness: written runbook with provider hotlines and account IDs, pre-agreed blackhole/flowspec communities tested in advance, dashboards and pps/bps alerting thresholds, gameday drills, and a status-page/comms owner distinct from the responder

## Follow-ups
- The traffic is only 4 Gbps but the firewall is falling over. What's happening and how does the response change?
- The attack shifts to legitimate-looking HTTPS GETs from a large residential botnet. What now?
- How do you decide between always-on scrubbing and on-demand redirection, and what does the failover latency cost you?
- After scrubbing is in place, how would you keep an attacker from finding and hitting your origin IPs directly?

## Sample answer
First three minutes I characterise it: interface utilisation and drops on transit, NetFlow top talkers, pps versus bps, packet sizes, source spread. If it's 100 Gbps of spoofed UDP reflection then nothing I do on my own edge helps — my pipe is already full — so the very first call is to my transit providers and scrubbing provider on the numbers in the runbook, and I redirect via BGP into scrubbing. In parallel, if the target is one VIP and I need the link back now, I announce that /32 with the provider's blackhole community. I'd say out loud that RTBH sacrifices that IP — the attacker gets what they want for that service — but it saves everything else behind the link. Flowspec is better where the provider supports it because I can drop by protocol, port and packet length instead of the whole destination. Meanwhile I make sure CoPP is protecting the router CPU so I don't lose BGP or SSH, and that the firewall's session table isn't the thing collapsing. Architecturally: anycast across POPs so no single site absorbs it all, always-on CDN or scrubbing in front with origin IPs hidden and ACLed to the provider's ranges, diverse and over-provisioned transit, and a tested runbook with pre-agreed communities and provider contacts — the worst time to learn the escalation path is during the attack.
