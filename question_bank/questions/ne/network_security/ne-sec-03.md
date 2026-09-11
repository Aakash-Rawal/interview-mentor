---
id: ne-sec-03
domain: ne
topic: network_security
difficulty: medium
tags: [segmentation, zero-trust, lateral-movement, blast-radius]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A compromised laptop on the corporate network was able to reach production database servers directly. What design changes would you make?

## What interviewers look for
- Frames it as a segmentation and blast-radius failure, not a malware problem
- Names the enforcement point and identity source rather than saying 'zero trust'
- Enumerates concretely what the laptop could reach and what it should have been able to reach
- Designs the access path for humans (bastion / identity-aware proxy, MFA, short-lived creds) as well as network policy
- Includes verification and detection — proves the new policy works and would catch the next attempt

## Strong answer covers
1. Blast radius first: list what that laptop could reach — every prod DB port, management VLAN, hypervisors, backups, CI runners — and how (flat routing, no interzone filtering, DB listening on 0.0.0.0 with a weak or shared credential)
2. Zone model with default deny between zones: user/corp, guest, DMZ, app tier, data tier, management/OOB; corp user subnets must have no route or no permit to data-tier ports at all, enforced at the DC edge firewall and not only by host config
3. Human access path: bastion/jump host or identity-aware proxy (SSO + MFA + device posture), short-lived credentials or certificates, session recording, break-glass account that is monitored and alerted on use; no direct laptop-to-DB path even for DBAs
4. Microsegmentation inside the DC: host firewalls, security groups, or SDN policy so app servers can reach the DB on 5432/3306 but DB-to-DB and DB-to-internet are denied; egress filtering to kill C2 and data exfil
5. Identity and credential hygiene: per-service accounts from a secrets manager rather than credentials in laptop config files, database-level allowlists, rotate everything the laptop touched, 802.1X/NAC on the campus so unknown devices land in quarantine
6. Detection: log and alert on east-west denies, VPC/NetFlow flow logs for new talker pairs, IDS at the DC chokepoint, DB audit logs for logins from unexpected source ranges, alerts on bastion bypass
7. Verification of the new policy: pre/post reachability matrix tested from a corp-network host (nmap/scripted probes) for every prod port, hit counters on the new deny rules, and a periodic automated reachability test in CI so drift is caught
8. Rollout without an outage: deploy in log-only/monitor mode first to find legitimate flows you'd break (backup agents, monitoring, deploy tooling), publish exceptions, then flip to enforce with a rollback plan and maintenance window

## Follow-ups
- A DBA says the jump host is too slow and asks for a direct exception 'temporarily'. How do you handle it technically and organisationally?
- How does this design change if the databases are managed cloud services rather than servers you own?
- The attacker already has valid VPN credentials for a legitimate DBA. Which of your controls still work?
- How do you prove segmentation is still intact six months later without another incident?

## Sample answer
The root cause is that the corp user network had a routable, permitted path to the data tier — this is a segmentation failure, not an endpoint failure. I'd start by writing the actual blast radius: from that laptop, which prod ports, management interfaces, hypervisors and backups were reachable? That list is the requirements document. Target design: zones with default deny between them — corp, guest, DMZ, app tier, data tier, management on OOB — and corp user subnets have no permitted path to the data tier at all. Human access goes through a bastion or identity-aware proxy with SSO, MFA and device posture, issuing short-lived credentials, with session logging; the enforcement point is the DC edge firewall plus host-level security groups, and the identity source is our IdP. Inside the DC I'd microsegment so app hosts reach the DB on its port and nothing else does, plus egress filtering so a compromised host can't reach C2. Detection: log east-west denies, flow logs alerting on new talker pairs, DB audit for logins from unexpected ranges. Rollout matters — I'd run the policy in log-only mode first to find the backup agent and monitoring flows I'd otherwise break, then enforce in a window. And I'd verify with a scripted reachability matrix from the corp network, run continuously, so drift shows up before an attacker does.
