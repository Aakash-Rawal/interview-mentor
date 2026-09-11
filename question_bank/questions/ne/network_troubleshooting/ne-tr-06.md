---
id: ne-tr-06
domain: ne
topic: network_troubleshooting
difficulty: medium
tags: [stp, loops, broadcast]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
CPU on every switch in a datacenter pod spikes and hosts see huge latency. It started after a new switch was cabled in. Diagnose and stop the bleeding.

## What interviewers look for
- Recognises the pattern from the symptom shape — all devices, correlated with a cabling change — instead of debugging one switch
- Mitigates first with the smallest reversible action, then investigates
- Names the specific counters and logs that confirm a loop rather than saying 'probably a loop'
- Explains the mechanism: why a L2 loop drives control-plane CPU, not just bandwidth
- Moves to systemic prevention and asks why the topology allowed it

## Strong answer covers
1. Reads the signature: simultaneous CPU spike on every switch in the L2 domain, host latency, correlated with a physical change — this is a broadcast/BUM storm from a layer-2 loop, not a per-device fault; control-plane CPU rises because flooded broadcast/ARP and BPDU/topology churn are punted to the CPU
2. Immediate mitigation with smallest blast radius: shut the newly cabled ports (the known change) first, confirm CPU and latency recover; not a reload, not shutting production uplinks — and have the rollback typed before applying
3. Confirming evidence: STP topology-change counters and TCN storms, root bridge changed unexpectedly (`show spanning-tree root`), ports in forwarding that should be blocking, MAC flapping/host-moving logs showing the same MAC oscillating between ports, interface utilisation pegged at line rate on the loop ports with broadcast counters exploding, CPU-queue/CoPP drop counters for BPDU/ARP
4. Root-cause candidates: new switch running no STP or a different mode/region (MST region mismatch, PVST vs MST, RSTP interop), STP disabled on the new links, two access ports patched together or a mis-cabled loop back into the same VLAN, a bridging host/hypervisor bridging two NICs, unidirectional link making STP fail (no UDLD), or the new switch winning root election with a low priority and dragging the topology
5. Checks whether the new switch became root and whether traffic was re-pathed through an undersized device — a topology change alone can congest without a hard loop
6. Verification: after shutting the links, confirm CPU returns to baseline, MAC table stops flapping, STP TC counters stop incrementing, host latency normal; then re-introduce the link one port at a time with STP verified and watch counters
7. Prevention: BPDU guard and root guard on access ports, loop guard and UDLD on inter-switch links, broadcast/multicast storm control thresholds, CoPP/control-plane protection, consistent STP mode and priorities with an explicit root and backup root, staging new switches with a known config before cabling, port descriptions, and change control requiring a pre-cabling config review
8. Asks the design question: why could a single mis-cabled device melt the whole pod — argues for smaller L2 domains, routed access/L3-to-the-ToR or EVPN-VXLAN so broadcast domains don't span the pod

## Follow-ups
- You shut the new links and CPU stays pegged. What now?
- Which control-plane protections would have contained this without any human intervention, and what would each have cost you?
- How would you tell a genuine loop apart from a single host flooding broadcast traffic, say a bad NIC or an ARP storm from a misbehaving app?
- Design answer: how would you re-architect this pod so one mis-cabled switch can't affect every device, and what do you give up?

## Sample answer
Every switch in the pod spiking at once, right after someone cabled a new switch in — that's a layer-2 loop and a BUM storm. The CPU spike is the giveaway: flooded broadcast and ARP plus STP topology churn get punted to the control plane, so it's not just bandwidth. Stop the bleeding first with the smallest reversible action: shut the newly cabled ports, since that's the known change, and confirm CPU and host latency recover. Then I gather the proof — STP topology-change counters and whether the root bridge moved, MAC flap logs showing the same address bouncing between ports, broadcast counters and utilisation pegged on the loop ports, and CoPP drops for BPDU and ARP. Root cause is usually the new switch not participating in STP properly: STP disabled, a different mode or MST region mismatch, or it won root election with a default low priority; it can also be a straight mis-cable back into the same VLAN or a host bridging two NICs. I bring the link back one port at a time with STP verified and watch the counters. Prevention is the real answer: BPDU guard and root guard on access ports, loop guard and UDLD between switches, storm control and CoPP, an explicit root and backup root, and staging switch configs before anyone patches a cable. Longer term, shrink the L2 domain — routed access so one mistake can't reach the whole pod.
