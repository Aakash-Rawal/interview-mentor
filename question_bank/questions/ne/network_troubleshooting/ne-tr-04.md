---
id: ne-tr-04
domain: ne
topic: network_troubleshooting
difficulty: easy
tags: [dhcp, layer2]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
New machines in one rack aren't getting DHCP addresses; older ones still work. Where do you start?

## What interviewers look for
- Separates 'does the DISCOVER get to the server' from 'does the OFFER get back' before guessing
- Uses a capture at the relay and at the server rather than only reading configs
- Knows the broadcast/relay mechanics of DHCP well enough to predict where it would fail
- Notices the 'new hardware / new rack' clue and asks what was provisioned differently
- Checks the pool numerically instead of assuming it's fine

## Strong answer covers
1. Defines scope precisely: is it every host in the rack or only new MACs, does a static IP work on the same port (proving L1/L2/L3 are fine and isolating DHCP), which VLAN, and what does the client log say (no OFFER vs NAK vs duplicate address)
2. Checks the pool first because it's cheap: scope utilisation and free addresses, lease duration vs churn, abandoned/BAD_ADDRESS entries, old leases still holding addresses — a rack of new machines can exhaust a /24 scope that was sized years ago
3. Checks the relay: `ip helper-address`/DHCP relay configured on the new SVI, correct server addresses, the SVI is up with an address in the right subnet, and the option-82/giaddr the relay stamps matches a subnet the server has a scope for
4. Checks L2 on the new ToR: VLAN exists locally and is allowed on the uplink trunk (`show vlan`, `show interface trunk`), native VLAN mismatch, access port in the right VLAN, MAC learned in the table
5. Checks DHCP security features on the new switch: DHCP snooping enabled for the VLAN with the uplink/relay port not configured as trusted, snooping rate limits, port-security MAC limits, IP source guard, or BPDU/storm control side effects
6. Captures the protocol exchange and locates the break: `tcpdump -ni <if> port 67 or port 68` at the access switch, the relay SVI, and the DHCP server — DISCOVER seen at relay but not at server → relay/routing/firewall; DISCOVER at server but no OFFER → scope/exhaustion/server policy; OFFER at server and not at relay → return path/ACL; OFFER at relay and not at client → snooping/trust or VLAN
7. Knows the message flow and fields to read: DISCOVER/OFFER/REQUEST/ACK, giaddr set by the relay, broadcast flag, relay unicast to server on UDP/67, server replies to giaddr, and that a missing OFFER differs from a NAK (wrong subnet/conflicting scope)
8. Fix and prevention: correct the specific gap, verify by bouncing a client port and watching the full DORA in the capture; prevention is a provisioning checklist/template for new ToRs (helper-address, snooping trust, trunk allow-list), scope utilisation alerting at 80%, and config diff against a golden template

## Follow-ups
- The DISCOVER reaches the server and the server logs an OFFER, but the client never gets an address. Give me the two most likely causes and the capture that separates them.
- Hosts do get an address but it's from the wrong subnet. What's the mechanism?
- How would PXE boot complicate this, and what extra options/relay behaviour would you check?
- Redundant DHCP servers: how do the failover/split-scope models change your exhaustion analysis?

## Sample answer
First I narrow it: is it the whole rack or only new MACs, and does a manually configured static address on the same port work? If static works, L1 through L3 are fine and it's purely DHCP. Then I check the cheap thing — scope utilisation and free leases. A new rack landing in an old /24 scope with long leases and abandoned addresses will just run out. Next, the new-rack clue makes me suspect provisioning: is ip helper-address on the new SVI pointing at the right servers, is the VLAN allowed on the uplink trunk, and is DHCP snooping enabled with the uplink port left untrusted — that silently drops OFFERs coming back down. Rather than argue about configs I capture. tcpdump on port 67 and 68 at the access switch, at the relay SVI, and at the server. That tells me exactly where it stops: DISCOVER at the relay but not the server means relay or a firewall; DISCOVER at the server with no OFFER means scope or policy; OFFER leaving the server but not reaching the client means the return path or snooping trust. I also check giaddr matches a subnet the server has a scope for. Fix, then bounce a port and watch the full DORA. Prevention: a ToR provisioning template and an 80% scope-utilisation alert.
