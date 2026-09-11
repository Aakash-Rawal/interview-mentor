---
id: ne-tr-03
domain: ne
topic: network_troubleshooting
difficulty: medium
tags: [packet-loss, interfaces]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A link between two switches shows 0.5% packet loss. Walk me through isolating whether it's the optic, the fibre, the port, or congestion.

## What interviewers look for
- Reads counters on both ends and distinguishes error counters from drop counters
- Forms a hypothesis before swapping hardware, then swaps one variable at a time
- Quantifies before and after with a controlled test rather than eyeballing pings
- Handles blast radius: drains the link before removing it from service
- Understands microbursts and why average utilisation graphs can look innocent

## Strong answer covers
1. Clears and re-reads interface counters on both ends and does the direction arithmetic: input errors/CRC/FCS on side B mean corruption arriving from A, so the fault is in A's transmit path or the fibre; symmetric errors on both ends suggest the fibre/connector
2. Distinguishes signatures: CRC/FCS, runts, giants, symbol errors, input errors → physical layer (dirty or damaged connector, bent/kinked fibre, failing optic, wrong optic type or wavelength, mismatched SMF/MMF); output drops/queue drops with zero errors → congestion or buffer exhaustion
3. Reads optic DOM on both ends: Tx and Rx power against the optic's sensitivity range, temperature, bias current; compare to the same optic model on a healthy link and to the loss budget for the span
4. Controlled quantified test rather than anecdote: `ping -f`/large-count ping, or iperf3 UDP at a known rate and TCP for throughput, plus `ethtool -S`/`show interface` deltas; record the baseline loss rate so you can prove the fix
5. Swap sequence, one variable at a time, with re-measure after each: clean/reseat connectors first, then swap the optic on the suspect transmit side, then the patch/fibre, then move to a different port/ASIC, then the line card — stop when the loss moves or clears
6. Congestion path: check output drops against queue counters and per-queue stats, look for microbursts (drops with 20% average utilisation means sub-second bursts — use high-resolution polling, 1s counters, or buffer/latency histograms), check LACP/ECMP hash imbalance putting elephant flows on one member
7. Blast radius: before touching anything, identify what rides the link and whether there's an ECMP/LACP sibling; drain by costing out (raise IS-IS/OSPF metric or LACP min-links / remove from bundle) and confirm traffic moved before shutting the port
8. Prevention: alert on CRC error rate (errors per second/per million packets, not just link state), optic DOM thresholds, BFD on routed links so a lossy-but-up link is detected, dropping links with rising error rates automatically, and pre-deployment fibre certification/loss-budget records

## Follow-ups
- CRC errors are only on one side and only when utilisation is high. What does that suggest and how do you confirm it?
- You swapped the optic and the fibre and the errors persist on the same port. What's left, and what do you do next?
- Zero errors and zero output drops, but iperf still shows 0.5% loss end to end. Where is it?
- How does 0.5% loss on this link affect a TCP transfer across a 40ms RTT versus a 1ms RTT, and why does that matter for the urgency?

## Sample answer
First I confirm the loss with a controlled test and write down the number — iperf UDP at a fixed rate plus a long flood ping — so I can prove the fix later. Then counters on both ends after a clear. The split is simple: CRC and input errors mean physical corruption, output drops with no errors mean congestion. Direction matters: CRCs arriving on B point at A's transmit side or the fibre between them. I pull optic DOM on both ends and compare Tx and Rx power to the optic spec and to a healthy twin link; low Rx with a clean fibre budget is a dirty connector or a dying laser. Then I change one variable at a time, re-measuring each time: reseat and clean, swap the optic on the suspect transmit side, swap the patch fibre, then move to a different port on a different ASIC. If it's drops instead of errors, I look at per-queue counters and poll at one-second resolution, because a link at 20% average can still microburst to line rate, and I check LACP hash imbalance. Before any of the disruptive steps I drain the link — cost it out or pull it from the bundle and confirm traffic moved — then shut it. Prevention: alert on CRC rate and DOM thresholds, and BFD so a lossy-but-up link gets taken out.
