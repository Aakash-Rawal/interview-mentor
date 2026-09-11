---
id: ne-fun-01
domain: ne
topic: networking_fundamentals
difficulty: easy
tags: [subnetting, cidr]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
How many usable hosts are in a /26? Show your working, and give a case where you would use a /30 or /31.

## What interviewers look for
- Derives the answer from 2^(32-prefix) rather than reciting a memorised table
- Knows the network/broadcast exception and that /31 and /32 are special cases
- Picks the prefix from a real design constraint (address conservation, point-to-point links) rather than habit
- Comfortable computing block boundaries and ranges on the spot
- Mentions operational caveats: older gear or some platforms not supporting /31, loopbacks as /32

## Strong answer covers
1. /26 = 2^(32-26) = 64 addresses, minus network and broadcast = 62 usable; states the mask 255.255.255.192
2. General formula usable = 2^(32-prefix) − 2, with /31 and /32 as exceptions
3. Block boundaries for /26: .0, .64, .128, .192 — e.g. 10.1.5.77/26 → network 10.1.5.64, broadcast 10.1.5.127, usable .65–.126
4. /30 gives 4 addresses / 2 usable; classic choice for router-to-router point-to-point links
5. /31 gives 2 usable with no network/broadcast (RFC 3021), halving address burn on P2P links
6. Why /31 is preferred on modern gear: no wasted addresses at scale (a spine-leaf fabric with hundreds of links), supported by mainstream NOSes; caveat that some legacy/embedded devices or management interfaces still need /30
7. /32 for loopbacks and host routes; mentions that IPv6 uses /127 for the equivalent P2P case and /64 per LAN

## Follow-ups
- You need to carve 10.20.0.0/22 into subnets for 4 racks of ~50 hosts each plus point-to-point uplinks. How do you lay it out, and what do you leave room for?
- Someone configures a host as 10.1.5.130/26 and another as 10.1.5.77/26 and expects them to talk directly. What actually happens on the wire?
- How does subnetting change for IPv6 — would you ever hand out something smaller than a /64 on a LAN, and why not?
- What breaks if two adjacent routers are configured with mismatched masks on the same link, say /30 on one side and /29 on the other?

## Sample answer
A /26 leaves 6 host bits, so 2^6 = 64 addresses, minus the network and the broadcast address gives 62 usable. The mask is 255.255.255.192, and the blocks land on .0, .64, .128, .192 — so 10.1.5.77/26 is network 10.1.5.64, broadcast 10.1.5.127, usable .65 to .126. The general rule is 2^(32−prefix) − 2, with /31 and /32 as the exceptions. For point-to-point links — router to router, or a leaf-to-spine uplink — you only ever need two addresses, so a /30 gives you 4 addresses and 2 usable, wasting half. RFC 3021 /31 removes the network and broadcast concept entirely on point-to-point links and gives you both addresses as usable, so you burn two addresses instead of four. On modern gear that's what I default to: in a fabric with a few hundred uplinks that's a meaningful chunk of a /24 saved, and it keeps the addressing plan tidy. I'd stick to /30 only where legacy or embedded kit doesn't support /31. Loopbacks get /32s, and the IPv6 equivalent is /127 on P2P with /64 everywhere else.
