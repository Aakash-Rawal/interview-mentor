---
id: ne-fun-04
domain: ne
topic: networking_fundamentals
difficulty: easy
tags: [arp, switching, vlan]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Two hosts on the same switch and same VLAN can't ping each other, but each can ping the gateway. What would you check?

## What interviewers look for
- Suspects the hosts before the network, given the gateway is reachable from both
- Reasons from the evidence: gateway works, so port, VLAN and physical are basically proven for each host individually
- Names concrete commands and what each result would rule in or out
- Considers asymmetric cases — one direction works, the other doesn't
- Escalates to a capture as the arbiter rather than arguing from config

## Strong answer covers
1. Uses the evidence: both reaching the gateway proves link, VLAN membership, addressing sanity and switch port health for each host, so the fault is likely host-side or a policy that blocks host-to-host specifically
2. Host firewall as the leading hypothesis (Windows Defender Firewall public profile blocking ICMP, iptables/nftables, host-based EDR); test with `iptables -L -n`/`Get-NetFirewallProfile`, or temporarily allow ICMP
3. Check ARP resolution: `arp -a` / `ip neigh` on each host — incomplete entry means the request or reply isn't getting through, a complete entry with no ping reply points at filtering
4. Subnet mask mismatch: e.g. /26 vs /24 so one host thinks the other is off-subnet and sends to the gateway instead of ARPing directly; verify with `ip addr` and `ip route get <peer>`
5. Switch-side isolation: protected/isolated ports, private VLAN (isolated vs community), port ACLs, or a wireless client-isolation setting
6. Duplicate IP or a stale/incorrect static ARP entry — check for MAC conflicts on the switch CAM table (`show mac address-table`)
7. Confirm on the wire: tcpdump on both hosts for ICMP and ARP, plus a SPAN/monitor session or `show mac address-table` to prove the frames reach the far port
8. Sanity-test with something other than ping (nc -zv to an open port) since ICMP may be blocked while TCP works

## Follow-ups
- Host A can ping B but B can't ping A. What does that asymmetry narrow it down to?
- It turns out both hosts are VMs on the same hypervisor. What changes about where you look?
- How would private VLANs produce this symptom, and why would that be deliberate in a design?
- You see ARP replies arriving at host A in tcpdump but the ARP table still shows incomplete. What's going on?

## Sample answer
The fact that both reach the gateway is doing a lot of work for me: it proves each host's link, VLAN, IP config and switch port are broadly fine. So I stop blaming the network and start with the hosts. My first bet is a host firewall — Windows in the public profile blocks inbound ICMP by default, and EDR agents do similar. I'd check `iptables -L -n` or the Windows profile and try a TCP test with `nc -zv` too, because ICMP might be blocked while the service is reachable. Next, ARP: `ip neigh` on each host. An incomplete entry means we're not even resolving; a complete entry with no echo reply points squarely at filtering. Then masks — if one is a /26 and the other a /24 they'll disagree about whether they're on-link, so I'd run `ip route get <peer>` and see whether it wants to go via the gateway. After that, the switch: protected ports, private VLAN isolation, port ACLs, or client isolation on wireless, all of which permit gateway traffic and block peer traffic by design. I'd also check the MAC address table for a duplicate IP. If nothing is conclusive, tcpdump on both hosts simultaneously settles it — whoever isn't seeing the frames tells me which side to dig into.
