# Network Security (Network Engineering)

## Firewalls & ACLs
- **Stateful firewall** tracks connection state; allows return traffic automatically.
- **Stateless ACL** evaluates each packet independently; must permit both directions.
- Order matters: ACLs are first-match; put specific denies before broad permits.
- Default-deny is the secure baseline; allow only what's needed.

## VPNs
- **IPsec** (L3): site-to-site tunnels. IKE phase 1 (auth, establish secure channel)
  → phase 2 (negotiate IPsec SAs). ESP for encryption, AH for integrity (rarely alone).
- **SSL/TLS VPN** (L7): client remote access via browser/agent; easier through NAT/firewalls.
- Common breakage: MTU/MSS clamping needed inside tunnels; mismatched IKE params.

## Zero Trust
- "Never trust, always verify" — no implicit trust from network location.
- Per-request authn/authz, device posture, least privilege, microsegmentation.
- Replaces the flat "hard shell, soft center" perimeter model.

## Segmentation
- VLANs / subnets / security groups isolate blast radius.
- Microsegmentation: policy between workloads, not just subnets.
- DMZ for internet-facing services, separated from internal networks.

## Common attacks & defences (NE framing)
- **DDoS** → anycast absorption, rate limiting, scrubbing, SYN cookies.
- **ARP spoofing** → dynamic ARP inspection, port security.
- **DNS poisoning** → DNSSEC, validating resolvers.
- **MITM** → TLS everywhere, mutual TLS for service-to-service.
- **Lateral movement** → segmentation + zero trust contain it.

## TLS quick reference
- Handshake: ClientHello → ServerHello + cert → key exchange → Finished.
- mTLS: both sides present certs (common for service mesh).
- Debug with `openssl s_client -connect host:443 -servername host`.
