---
id: ne-fun-03
domain: ne
topic: networking_fundamentals
difficulty: medium
tags: [tcp, handshake, flow]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Walk through everything that happens on the wire when a laptop on Wi-Fi loads https://example.com for the first time, from DHCP through the first byte of HTML.

## What interviewers look for
- Keeps the layers strictly separated and never confuses L2 addressing with L3
- Volunteers where each step would fail and what the user-visible symptom would be
- Mentions caching and state at every level (DNS TTL, ARP table, NAT table, TLS session resumption)
- Handles the on-link vs off-link decision explicitly via the subnet mask
- Paces the answer — depth where it matters, doesn't rat-hole on one layer

## Strong answer covers
1. L1/L2: Wi-Fi association and 802.11 auth, then DHCP DISCOVER/OFFER/REQUEST/ACK (broadcast, relay/helper address if the server is off-subnet) returning IP, mask, default gateway, DNS servers and lease time
2. DNS: stub resolver checks local cache and hosts file, then queries the recursive resolver, which walks root → .com TLD → authoritative, returning A/AAAA with a TTL; answers cached, NXDOMAIN negatively cached
3. Destination is off-subnet by mask comparison, so the host ARPs for the default gateway's MAC (broadcast who-has, unicast reply); IPv6 uses Neighbor Discovery instead
4. TCP three-way handshake: SYN with ISN, MSS, window scale and SACK options, SYN-ACK, ACK; ephemeral source port chosen by the client
5. NAT/PAT at the edge rewrites source IP and port and creates a state table entry with a timeout
6. TLS: ClientHello with SNI and ALPN → ServerHello, certificate, ECDHE key exchange → Finished; TLS 1.3 is 1-RTT (0-RTT on resumption); chain validation against trust store, OCSP/CRL revocation check
7. HTTP request/response over the established connection; keep-alive reuse, HTTP/2 multiplexing over one connection
8. Routing hop by hop: each router does longest-prefix match, decrements TTL and recomputes checksum, rewrites source/destination MAC each hop while the L3 header is otherwise untouched except for NAT
9. Maps failures to layers: no DHCP → 169.254 link-local; DNS failure → name doesn't resolve but the IP works; SYN with no SYN-ACK → firewall/black hole; RST → nothing listening; cert error → TLS layer

## Follow-ups
- The page loads for IPv4 users but hangs for dual-stack clients. Where do you look?
- Where exactly does a CDN or anycast change this story, and what does that mean for debugging a per-user problem?
- Which of these steps can you skip on the second page load, and how much RTT does that save?
- The user is behind a captive portal. Which of these steps behave differently, and why does HSTS make that painful?

## Sample answer
First the laptop associates and authenticates to the AP at layer 2, then DHCP: DISCOVER, OFFER, REQUEST, ACK — broadcast, relayed if the server is off-subnet — which gives it an address, mask, default gateway, DNS servers and a lease. Then name resolution: the stub resolver checks its cache, otherwise asks the configured recursive resolver, which walks root, .com, then the authoritative servers and returns an A or AAAA with a TTL that everything caches. Now the host compares the destination against its own address and mask, decides it's off-subnet, and ARPs for the gateway MAC — broadcast who-has, unicast reply. IPv6 would use Neighbor Discovery. It opens TCP to port 443: SYN with an ISN, MSS, window scale and SACK, SYN-ACK, ACK, from an ephemeral source port. At the edge the NAT rewrites source IP and port and holds state. Then TLS: ClientHello with SNI and ALPN, ServerHello, certificate, ECDHE, Finished — one RTT on TLS 1.3 — and the client validates the chain. Then the HTTP GET and the response, with keep-alive so the connection is reused. Along the path each router does a longest-prefix match, decrements TTL, and rewrites the layer 2 headers; the IP header is otherwise untouched apart from TTL, checksum and NAT. Each stage has a distinct failure signature — 169.254 means DHCP, no SYN-ACK means a drop, RST means nothing listening.
