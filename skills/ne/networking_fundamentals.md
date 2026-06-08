# Networking Fundamentals (Network Engineering)

## OSI model (know what lives where)
| Layer | Name | Examples | Troubleshoot with |
|---|---|---|---|
| 7 | Application | HTTP, DNS, gRPC | curl, dig |
| 6 | Presentation | TLS, encoding | openssl s_client |
| 5 | Session | sockets | ss |
| 4 | Transport | TCP, UDP | ss, tcpdump |
| 3 | Network | IP, ICMP, routing | ping, traceroute, ip route |
| 2 | Data Link | Ethernet, ARP, VLAN | arp, ip neigh |
| 1 | Physical | cables, NIC, optics | ethtool, link lights |

Always isolate by layer: bottom-up (cable→IP→app) or split-half.

## TCP/IP essentials
- **TCP handshake**: SYN → SYN-ACK → ACK. Teardown: FIN/ACK both ways.
- **TCP vs UDP**: TCP = ordered, reliable, congestion-controlled; UDP = fire-and-forget (DNS, VoIP, QUIC base).
- **MSS/MTU**: default Ethernet MTU 1500; PMTU black holes cause hangs on large payloads only.
- **Ports**: well-known < 1024; ephemeral range for clients.

## Subnetting / CIDR
- `/24` = 256 addrs (254 usable), `/16` = 65,536, `/30` = 4 (2 usable, point-to-point links).
- Host bits = 32 − prefix; hosts = 2^hostbits − 2 (network + broadcast).
- Quick math: each step down in prefix doubles the block. `/25` = 128, `/26` = 64.
- RFC1918 private: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16.

## VLANs
- Layer-2 broadcast-domain segmentation. 802.1Q tags frames (12-bit VLAN ID, 4094 usable).
- Trunk ports carry multiple VLANs (tagged); access ports = one VLAN (untagged).
- Inter-VLAN routing needs an L3 device (router-on-a-stick or L3 switch SVI).

## ARP
- Resolves IP → MAC within a broadcast domain. `ip neigh` shows the cache.
- Gratuitous ARP announces ownership (used in failover / VIP takeover).
- ARP issues: duplicate IP, stale entries, proxy ARP misconfig.
