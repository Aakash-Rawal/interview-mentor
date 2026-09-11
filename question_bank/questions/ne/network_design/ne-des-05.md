---
id: ne-des-05
domain: ne
topic: network_design
difficulty: easy
tags: [campus, segmentation, redundancy, vlans]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Design the network for a 500-person office: users, printers, guest Wi-Fi, and a small server room. Focus on segmentation and what breaks if the core switch dies.

## What interviewers look for
- Segments by function with a reason for each VLAN, not VLAN-per-everything
- Is explicit and honest that a single core is a SPOF and either pairs it or states the accepted risk with a recovery time
- Thinks about the services that live behind the core — DHCP, DNS, Wi-Fi controller, RADIUS — not just switches
- Covers access-layer identity (802.1X, dynamic VLAN) and guest isolation properly
- Talks about spare hardware, config backup and restore time as part of the design

## Strong answer covers
1. VLANs per function with justification: users, voice (with QoS trust boundary), printers, guest, IoT/building systems, wireless, server room, management — inter-VLAN routing on SVIs at the core, ACLs between segments
2. Access layer: 802.1X with dynamic VLAN assignment and MAB fallback for printers/IoT, RADIUS redundancy, port security, plus a failure policy for when RADIUS is down (critical-auth VLAN)
3. Guest design: internet-only, isolated from all internal VLANs and from other guests (client isolation), separate DHCP/DNS scope, rate limiting, captive portal; guest traffic routed straight to the firewall
4. Core redundancy: a pair of switches with MLAG/stacking/VSS plus VRRP/HSRP or anycast gateway for first-hop redundancy; LACP uplinks from each access switch split across both core members; STP root and edge/portfast hygiene as the backstop
5. Wi-Fi: controller or cloud-managed APs, SSID-to-VLAN mapping, PoE budget per access switch, AP placement/survey, controller redundancy or local-switching fallback so APs survive controller loss
6. Service placement: DHCP and DNS with redundancy (two servers in the server room or a cloud/appliance pair), DHCP relay from SVIs, internal DNS, and NTP — say what happens to leases when they're unreachable
7. Single-core failure walk: all inter-VLAN routing and all uplinks die, so every VLAN is isolated and internet access is gone even though access switches are up; guest and internal both down; recovery = swap spare, restore config, measured in tens of minutes to hours
8. Cost-aware trade-off: pair the core (extra chassis, licences, cross-connects) versus a cold spare with a tested config restore — pick one and state the downtime the business is accepting; also cover UPS, firewall redundancy, ISP redundancy and out-of-band/console access
9. Operations: config backup, documented port map and IPAM, monitoring with alerting on uplinks and PoE, change windows

## Follow-ups
- The business will only fund one core. Write me the one-paragraph risk statement you'd get signed, with an expected downtime number.
- How do you stop a compromised IoT camera on the IoT VLAN from reaching finance's file server, given routing happens on the core?
- The guest network is saturating the internet link at lunchtime. What do you change, and where do you enforce it?
- How would you migrate this office from a single core to a redundant pair with minimal disruption?

## Sample answer
For 500 people I'd segment by function, not by floor: users, voice, printers, guest, IoT, wireless, server room and management. Inter-VLAN routing on SVIs at the core with ACLs between segments — IoT and printers get very little, guest gets internet only with client isolation and its own DHCP scope, handed straight to the firewall. Access layer runs 802.1X with dynamic VLAN assignment, MAB for printers and cameras, redundant RADIUS and a critical-auth VLAN so a RADIUS outage doesn't lock everyone out. Each access switch dual-uplinks with LACP, and I'd watch PoE budget for APs and phones. DHCP and DNS run as a redundant pair in the server room with relay from the SVIs. Now the honest part: with a single core, everything routes through one box. If it dies, every VLAN is islanded — no inter-VLAN, no internet, guest down too — even though the access switches are happily forwarding. Recovery is swap the spare and restore config: an hour if I've rehearsed it, a day if I haven't. So either pair the core with MLAG and VRRP so an access switch loses one uplink and nothing else, or I put the risk in writing with a downtime number and get it signed. I'd also want a UPS, config backups, and console/out-of-band access.
