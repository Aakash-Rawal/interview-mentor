---
id: ne-fun-02
domain: ne
topic: networking_fundamentals
difficulty: medium
tags: [tcp, mtu, pmtud]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Small requests work but large file transfers hang intermittently across a tunnel. What is your leading hypothesis and how do you confirm and fix it?

## What interviewers look for
- Reaches for MTU/PMTUD immediately from the 'small works, large hangs' signature rather than guessing at bandwidth or the application
- Proposes a decisive test that produces a number, not just 'I'd look at the tunnel config'
- Explains the mechanism — DF bit, ICMP type 3 code 4, firewall dropping it — not just the label
- Distinguishes fixes by blast radius and where they can be applied (tunnel endpoint vs every host)
- Confirms with a packet capture on both sides rather than trusting the config

## Strong answer covers
1. Names the symptom pattern: small packets/handshakes succeed, bulk transfer stalls after the first few packets — classic PMTUD black hole
2. Mechanism: tunnel encapsulation (GRE ~24B, IPsec ~50-70B, VXLAN ~50B) reduces usable MTU below 1500; senders set DF, an intermediate device must return ICMP type 3 code 4 'fragmentation needed', and a firewall or ACL is dropping it
3. Confirm with a DF-bit ping sweep: `ping -M do -s 1472` (1472+28=1500) and bisect down to find the largest size that passes; also `tracepath`/`tracepath6` to see where the MTU drops
4. Confirm with tcpdump on both tunnel endpoints: retransmissions of large segments, absent ICMP 3/4, or the frag-needed being generated but never arriving
5. Fix options: TCP MSS clamping on the tunnel interface (`ip tcp adjust-mss 1360` / iptables TCPMSS --clamp-mss-to-pmtu), lower the tunnel/interface MTU, or permit ICMP type 3 code 4 through the firewalls
6. Notes MSS clamping only helps TCP — UDP/QUIC/IPsec ESP still need correct MTU or ICMP
7. Checks whether jumbo frames are configured end to end if this is a DC link, and that MTU matches on both sides of every hop
8. Verifies the fix by re-running the DF ping and a real bulk transfer (scp/iperf3), not just by reading config

## Follow-ups
- MSS clamping fixed the TCP traffic but a UDP-based application is still failing on large payloads. What now?
- Why might this have worked fine for weeks and only started failing after a firewall rule change on a completely different device?
- How would you detect this proactively across a fleet of tunnels before users complain?
- The ICMP frag-needed is arriving but the sender ignores it. What could cause that?

## Sample answer
'Small works, large hangs' is the signature of an MTU/PMTUD black hole, and a new tunnel is the classic trigger. The tunnel adds encapsulation — GRE about 24 bytes, IPsec 50 to 70 — so the effective path MTU is below 1500. The sender emits 1500-byte segments with DF set, some device drops them and should send back ICMP type 3 code 4 'fragmentation needed', but a firewall is swallowing that ICMP, so the sender never learns and just retransmits forever. Handshakes and small requests are under the limit, so they work fine. To confirm I'd do a DF ping sweep from a client: `ping -M do -s 1472` and bisect down until it passes — that gives me the real path MTU — and run tracepath to see which hop it drops at. Then tcpdump on both tunnel endpoints to confirm the large segments leave one side and never arrive, and that no ICMP comes back. The fix I'd reach for first is MSS clamping on the tunnel interface, because it fixes every TCP flow at one place without touching hosts. Alongside that I'd get ICMP 3/4 permitted, since clamping does nothing for UDP or QUIC. Then re-run the ping sweep and a real bulk transfer to verify.
