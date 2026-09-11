---
id: ne-rt-03
domain: ne
topic: routing
difficulty: medium
tags: [ospf, adjacency, mtu, troubleshooting]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Two OSPF neighbours are stuck in EXSTART/EXCHANGE. What causes that, and what if they're stuck in INIT instead?

## What interviewers look for
- Maps symptom to protocol phase — knows which packets are exchanged in each state
- Names MTU mismatch immediately for ExStart/Exchange and can explain the mechanism, not just the fact
- Gives a concrete verification command/test for each hypothesis rather than a list of guesses
- Orders checks by likelihood and cost to test
- Knows the full adjacency state machine

## Strong answer covers
1. Full state machine: Down → Init (hellos seen one-way) → 2-Way → ExStart → Exchange → Loading → Full, and DR/BDR election happens at 2-Way on multi-access links
2. ExStart/Exchange stuck: MTU mismatch — DBD packets carry the interface MTU and a neighbour rejects a DBD advertising an MTU larger than its own; large DBDs also get dropped on the smaller-MTU side
3. Second ExStart cause: duplicate router-IDs, so master/slave negotiation never settles; also unidirectional or asymmetric MTU (e.g. one side 9216, one side 1500 after a template change)
4. Verification for MTU: `show interface` on both sides, ping with DF bit at the exact MTU size (e.g. `ping <peer> size 9000 df-bit`), or `ip ospf mtu-ignore` as a diagnostic/workaround while noting it masks the real problem
5. Init stuck means hellos are one-way: the local router hears the neighbour but the neighbour doesn't list our router-ID in its hello neighbour list
6. Init causes: inbound ACL or firewall blocking 224.0.0.5, authentication type/key mismatch, area ID mismatch, hello/dead timer mismatch (10/40 broadcast default), mismatched network types (broadcast vs point-to-point), stub/NSSA flag mismatch, subnet-mask mismatch on a broadcast link, or unicast/multicast filtering on the L2 path
7. Note that timer and area/auth mismatches usually prevent adjacency entirely rather than sticking at Init — so a strong answer distinguishes 'no neighbour at all' from 'stuck at Init'
8. Tooling: `show ip ospf neighbor`, `show ip ospf interface`, debug/log of hello and DBD packets, packet capture on the segment

## Follow-ups
- They're stuck at ExStart and MTU matches on both sides. What else, and how do you prove it in under five minutes?
- You set mtu-ignore and the adjacency comes up Full. Is that a fix? What breaks later?
- The adjacency reaches Full but flaps every few minutes. How does your troubleshooting change?
- How would the same two problems present in IS-IS, and what's different about its adjacency formation?

## Sample answer
ExStart and Exchange are where the database description packets get exchanged, so the classic cause is an MTU mismatch. DBDs carry the interface MTU, and a router rejects a DBD advertising an MTU bigger than its own interface, so the two sides never get past master/slave negotiation. I'd check `show ip ospf interface` on both ends and then prove it with a DF-bit ping at the exact size — ping 9000 with don't-fragment. The other ExStart cause is duplicate router-IDs, where master/slave never resolves. I can set `ip ospf mtu-ignore` as a diagnostic, but I treat that as confirmation, not a fix, because mismatched MTU will bite me on large LSAs and on data traffic later. Init is a different story: it means I'm receiving the neighbour's hellos but my router-ID isn't in their neighbour list, so it's one-way. That's an inbound ACL or firewall dropping multicast to 224.0.0.5, an authentication type or key mismatch, an area ID mismatch, hello/dead timers out of sync — defaults are 10 and 40 on broadcast — or a network-type or subnet-mask mismatch. I'd capture on the segment to see whose hellos actually arrive, which tells me immediately which direction is broken.
