---
id: ne-sec-04
domain: ne
topic: network_security
difficulty: easy
tags: [ipsec, encryption, mtls, trade-offs]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Compare IPsec site-to-site VPNs with TLS-based approaches (e.g. WireGuard, mTLS service mesh) for connecting two datacenters. When would you choose each?

## What interviewers look for
- Starts from the requirement — what's the threat model, who owns the endpoints, what must be confidential — before naming a technology
- Distinguishes layer of enforcement (L3 tunnel vs per-connection identity) rather than treating them as interchangeable
- Raises MTU/MSS the moment a tunnel appears, unprompted
- Discusses operational cost honestly: key/cert lifecycle, throughput, failure modes, vendor support
- Willing to combine them, and can say what each layer buys that the other doesn't

## Strong answer covers
1. Requirements framing: is the threat a passive tap on a leased line/dark fibre, a hostile transit provider, or lateral movement inside the DC? Who owns the endpoints (routers you control vs third-party apps)? Is there a compliance mandate naming FIPS/approved suites?
2. IPsec site-to-site: L3, transparent to every app including legacy and non-IP-aware protocols, native in router/firewall hardware with crypto offload, IKEv2 with rekeying, mature and audited; costs are ~50-70+ bytes of overhead, MTU/PMTUD black-hole problems, IKE/SA debugging pain, NAT-T, and phase-2 selector complexity
3. WireGuard: much smaller codebase, single modern cipher suite (Noise/ChaCha20-Poly1305/Curve25519), fast in the kernel, trivially configured with public keys and allowed-IPs; costs are weak enterprise router support, no crypto agility, no built-in per-user AAA, roaming/keepalive semantics, and it's usually a Linux host doing the work rather than the edge router
4. mTLS / service mesh: per-connection workload identity (SPIFFE IDs or cert SANs), authorisation policy per service and method, protects against a compromised network path AND a compromised neighbouring host, works over any transport including the public internet; costs are that every app or sidecar must implement it, certificate issuance/rotation/revocation lifecycle, CPU and latency per connection, and non-HTTP or legacy traffic gets left out
5. MACsec as the other option for the DC-to-DC case: line-rate L2 encryption on the physical link, negligible operational overhead, but hop-by-hop only — it protects the fibre, not an untrusted intermediate router
6. MTU/MSS handling every time: reduce interface MTU or set `ip tcp adjust-mss` (~1360-1400) on tunnel interfaces, allow ICMP fragmentation-needed for PMTUD, watch out for DF-bit and UDP apps that can't be MSS-clamped
7. Failure and operational modes: does the tunnel fail closed (traffic drops) or open (plaintext over the WAN)? Rekey-induced blips, single-tunnel bandwidth ceilings and the need for multiple SAs/ECMP to scale beyond one core, HA/state on failover, and monitoring for tunnel down and cert expiry
8. Recommendation shape: IPsec or MACsec on the DC interconnect for blanket coverage of all traffic including legacy, plus mTLS between services for identity and authorisation; defence in depth because the tunnel only proves the link is protected, not who is calling whom

## Follow-ups
- You need 40 Gbps between the sites. How does that change the choice, and what actually limits IPsec throughput?
- One team says the encrypted tunnel makes troubleshooting impossible — no visibility for the IDS. How do you respond?
- Certificates in the mesh expire in 24 hours and the CA becomes unreachable. What happens, and how do you design around it?
- The link is a private, contractually-dedicated circuit. Make the argument for and against encrypting it at all.

## Sample answer
I'd ask what I'm defending against and who owns the endpoints. If the threat is a tap on a carrier circuit and I need everything — including legacy, non-TCP and management traffic — covered without touching applications, that's a network-layer job: IPsec between the edge routers, or MACsec if it's a single dark-fibre hop, because MACsec is line-rate and nearly free operationally but only protects one hop. IPsec is transparent, hardware-offloaded and mature; the costs are overhead and MTU, so I'd clamp MSS around 1360-1400 on the tunnel and make sure ICMP fragmentation-needed isn't filtered, or I'll get intermittent black-holing of large flows only. WireGuard is attractive when both ends are Linux hosts I control — simpler config, fast, modern crypto — but it has thin enterprise router support and no per-user AAA, so I'd use it for host-to-host or cloud overlays, not as a carrier-grade DCI. mTLS is a different axis: it gives per-connection workload identity and authorisation, so it also protects me from a compromised host inside the same DC, which no tunnel does. The cost is every service must speak it, plus cert issuance and rotation. In practice I'd do both: IPsec or MACsec on the interconnect for blanket coverage, mTLS between services for identity — and I'd check whether the tunnel fails closed or leaks plaintext when it drops.
