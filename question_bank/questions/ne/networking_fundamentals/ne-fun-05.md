---
id: ne-fun-05
domain: ne
topic: networking_fundamentals
difficulty: hard
tags: [tcp, congestion, performance]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A 10 Gbps link between two datacenters 80 ms apart only achieves 200 Mbps on a single TCP flow. Why, and what would you change?

## What interviewers look for
- Computes the bandwidth-delay product rather than hand-waving about 'tuning'
- Separates window-limited from loss-limited before proposing fixes
- Knows that a single flow is a distinct problem from aggregate link utilisation
- Proposes a measurement plan (iperf3 with varying streams and window sizes) that discriminates between hypotheses
- Weighs parallel streams as a pragmatic workaround versus fixing the root cause

## Strong answer covers
1. BDP calculation: 10 Gbps × 0.08 s = 800 Mbit ≈ 100 MB of data must be in flight to fill the pipe; conversely 200 Mbps × 80 ms ≈ 2 MB, which smells like a ~2 MB effective window
2. Throughput ≤ window / RTT; window scaling (RFC 1323/7323) must be negotiated in the SYN or the window caps at 64 KB
3. Tune Linux socket buffers: net.ipv4.tcp_rmem / tcp_wmem maxima, net.core.rmem_max / wmem_max, tcp_window_scaling=1, and check the application isn't calling setsockopt with a small fixed SO_SNDBUF/SO_RCVBUF (which disables autotuning)
4. Check for loss: `ss -ti` for retransmits/cwnd/rtt, netstat -s counters, or iperf3 retransmit column — Mathis says throughput ∝ MSS/(RTT·√loss), so even 0.01% loss is crippling at this RTT
5. Congestion control choice: CUBIC collapses and recovers slowly on loss at high BDP; BBR is far more tolerant of shallow random loss — but note BBR's fairness trade-offs
6. Measurement plan: iperf3 single stream vs `-P 8`, with `-w` to force window sizes; if 8 streams fill the link the path is fine and it's a per-flow window or loss problem, not capacity
7. Other suspects: middleboxes stripping window scale or rewriting MSS, a shaper/policer at 200 Mbps, NIC offload/ring buffer issues, interface errors/discards, or a hop with a small buffer causing tail drop
8. Parallel streams or a multi-stream tool (rsync in parallel, GridFTP-style, or object storage multipart) as a legitimate workaround when you can't fix the endpoints

## Follow-ups
- Eight parallel streams get you to 9 Gbps. What does that tell you, and would you ship that as the fix?
- You switch to BBR and throughput jumps. What risk have you just introduced for other traffic sharing that path?
- How would you tell the difference between a policer at 200 Mbps and a window limit, from the endpoint alone?
- The same tuning gives no improvement on a 1 ms intra-DC path. Why would you expect that?

## Sample answer
First the arithmetic: bandwidth-delay product is 10 Gbps times 80 milliseconds, about 100 megabytes that has to be in flight to keep the pipe full. Going the other way, 200 Mbps at 80 ms is roughly a 2 MB window — which is suspiciously like a socket buffer cap or window scaling not being in play. So my first hypothesis is window-limited, not capacity-limited. I'd check `ss -ti` during a transfer for the send window, cwnd, RTT and retransmits, and confirm window scaling was negotiated in the SYN with a capture — some middleboxes strip it. Then raise net.core.rmem_max/wmem_max and tcp_rmem/tcp_wmem, and check the application isn't setting a fixed SO_SNDBUF, which kills autotuning. The second hypothesis is loss. At 80 ms RTT, Mathis tells you throughput falls with the square root of loss, so even 0.01% will pin you near this number and CUBIC will recover painfully slowly. If `ss -ti` shows retransmits, I'm hunting errors, discards or a policer along the path rather than tuning buffers. The discriminator is iperf3: single stream versus `-P 8`. If eight streams fill the link, the path has capacity and it's per-flow window or loss. Fixes in order: buffer tuning, fix the loss, consider BBR, and parallel streams as a pragmatic stopgap.
