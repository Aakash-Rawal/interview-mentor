# Network Security — Network Engineering

## What this interview actually tests
Threat-model first, then controls, then blast radius when a control fails or misfires.
Scored on threat modeling, control selection, blast-radius awareness, root-cause precision,
and fix-plus-prevention. Many prompts are "a change broke production" or "an attacker got
further than they should have" — both reward precise, layered reasoning.

## Framework
1. **Assets & trust boundaries** — what must be protected, who talks to whom legitimately.
2. **Threats** — external (DDoS, hijack, scanning), lateral (compromised host), insider/
   misconfiguration (the most common outage cause).
3. **Controls by layer** — edge, segmentation, host, identity, control-plane.
4. **Detection** — flow logs, IDS, route monitoring, config drift.
5. **Failure of the control** — fail open or closed? what breaks? how do you roll back?

## ACLs and firewalls — the bugs
- **First match wins**; a new deny above an allow breaks traffic; **implicit deny** at the end.
- **Stateless** ACLs need the **return** traffic allowed explicitly (ephemeral ports);
  stateful firewalls track sessions — but only if they see both directions (asymmetry!).
- Wrong mask/wildcard, wrong direction (in/out), wrong interface, object-group typo.
- Safe change process: hit counters before/after, diff review, canary device, maintenance
  window, rollback typed first, narrow rules over broad ones.
- Stateful firewall failover needs **state sync** or long-lived sessions die.

## Segmentation
- Zones: user, guest, server, DB, management, DMZ; deny by default between zones.
- Corp laptops should never route to production data; bastions/jump hosts or identity-aware
  proxies, MFA, short-lived credentials.
- **Microsegmentation** in the DC (host firewalls, security groups, SDN policy) limits lateral
  movement; log east-west denies.
- Private VLANs / port isolation for untrusted L2 neighbours; 802.1X for port access.
- Blast radius question: "if this host is compromised, what can it reach?" — answer with a list.

## Edge protections
- **DDoS**: volumetric (saturate links) vs protocol (SYN flood, state exhaustion) vs
  application (L7). Now: engage upstream scrubbing, RTBH (blackhole the victim /32 — sacrifices
  it to save the link), flowspec, edge rate limits, SYN cookies. Later: anycast + scrubbing
  provider/CDN in front, over-provisioned edge, CoPP for control plane, runbook and contacts.
- **BGP hygiene**: prefix-lists in/out, max-prefix, RPKI ROAs for your space + ROV at the
  edge, IRR objects, bogon filters, GTSM/TTL security, MD5/TCP-AO on sessions, route
  monitoring (RIS/BGPalerter) for hijacks/leaks. Hijack response: announce more-specifics,
  call upstreams; limits: more-specific hijacks and providers that don't filter.
- **DNS**: DNSSEC, rate limiting, no open resolvers, split-horizon.

## Encryption in transit
| Option | Layer | Strengths | Costs |
|---|---|---|---|
| IPsec site-to-site | L3 | transparent to apps, router-native, mature | MTU overhead, PMTUD issues, key mgmt |
| WireGuard | L3 | simple, fast, modern crypto | less enterprise gear support |
| MACsec | L2 | line-rate hop-by-hop on links | per-hop only, hardware dependent |
| TLS / mTLS | L4+ | per-connection identity, app-aware, no network dependency | every app must do it; cert lifecycle |
Choose by who owns the endpoints and what needs protecting; mention MTU/MSS every time a
tunnel appears.

## Control-plane and device security
Management on an OOB network, AAA (TACACS+/RADIUS) with per-command authz, SSH only,
config backups + drift detection, NTP (logs and certs depend on it), SNMPv3, CoPP, disable
unused services, firmware patching cadence, logging to a central SIEM.

## Detection and response
Flow logs (NetFlow/sFlow/VPC flow logs) for lateral movement, IDS/IPS at chokepoints,
anomaly alerts on new talkers, route-change alerts, config change alerts. Response: contain
(isolate the host/port, revoke creds) → preserve evidence → eradicate → recover → postmortem.

## Common mistakes
- Adding a rule without checking ordering, direction, or return traffic.
- "Zero trust" as a slogan without naming the enforcement point and identity source.
- Forgetting the control plane (a router's own CPU) as a target.
- RTBH without saying it sacrifices the victim; DDoS plan with no upstream engagement.
- No rollback or verification step in a security change.

## Practice prompts
- ACL meant to block one subnet broke production — reason, fix safely, prevent.
- Compromised corp laptop reached prod DBs — redesign.
- Volumetric DDoS saturating transit — first 10 minutes, then architecture.
- Detect and respond to a prefix hijack; what prevents it.
- IPsec vs WireGuard vs mTLS for connecting two DCs.
