---
id: pe-tr-03
domain: pe
topic: troubleshooting
difficulty: medium
tags: [intermittent, networking, tcp, observability]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Users report intermittent 'connection failed' errors, but every time you test the service it works. What is your approach to catching an intermittent issue?

## What interviewers look for
- Refuses to guess; converts vague reports into specifics and a measured rate
- Determines whether the failure is even visible server-side, which localises it above or below the app
- Slices by dimension to find the pattern rather than hunting randomly
- Builds a reproduction/observation harness (continuous probe, sampled capture) instead of hoping to see it live
- Knows the classic intermittent-connection signatures and their evidence

## Strong answer covers
1. Get specifics from reporters: exact error string and error code, client library and version, precise timestamps with timezone, client IP/region/ISP, request ID, whether it's on first connection or a reused one, and whether retry succeeds immediately
2. Quantify: is 2% visible in LB/access logs and metrics, or invisible server-side? If the app never saw the request, the failure is below/before it — DNS, TCP, TLS, NAT, LB — which halves the search space immediately
3. Slice every dimension for a pattern: availability zone, LB node, backend host, client version, DNS resolver, mobile vs wifi, time-of-day, payload size, and per-backend error rate (one bad backend in 50 gives ~2%)
4. Build observation instead of waiting: high-frequency synthetic probes from multiple vantage points (inside VPC, other region, mobile network), client-side error telemetry with request IDs, raise sampling/log verbosity temporarily, and a ring-buffer `tcpdump -s0 -W 20 -C 100 'tcp[tcpflags] & (tcp-rst|tcp-syn) != 0'` triggered around failures
5. Check idle-timeout and keepalive mismatches: LB or NAT idle timeout shorter than the client's keepalive means the first request on a reused connection gets a RST — the classic 'works when I test it' signature; also server `keepalive_timeout` vs client pool max idle
6. Check kernel/network exhaustion counters: `nstat -az`/`netstat -s` for TcpExtListenOverflows, ListenDrops, SYN retransmits and ephemeral-port or conntrack table exhaustion (`conntrack -C` vs `nf_conntrack_max`), `ss -lnt` Recv-Q against backlog, plus MTU/PMTU blackholes for large payloads only
7. Check DNS: multiple A records where one endpoint is bad, TTL and negative caching, resolver differences, and health-check flapping adding/removing backends (correlate LB health-check state changes with the failure timestamps)
8. Close the loop: once a hypothesis is formed, state what you'd expect to see if it were true and check that; then fix, verify the residual rate drops from 2% to baseline with the prober, and add the missing signal (client-side error rate SLI, RST counter alert, health-check flap alert) so it's detected next time

## Follow-ups
- `nstat` shows TcpExtListenOverflows incrementing on three of twenty backends. Walk me from that counter to a fix.
- The failures only affect requests larger than 1400 bytes and only from one ISP. What's your hypothesis and how do you confirm it?
- How would you instrument clients so you can measure this class of failure permanently without shipping a debug build every time?
- At what point do you stop investigating a 2% intermittent error, and how do you justify that decision?

## Sample answer
The first thing I'd do is stop testing by hand and turn reports into data: exact error string, client library, timestamps with timezone, client IP and region, request ID, and whether it's the first request on a fresh connection or a reused one.

Then the key split: is the failure visible server-side? If the LB and access logs show the request, it's an app or backend problem. If nothing appears, the failure is below the app — DNS, TCP, TLS, NAT or LB — and that halves the search space. I'd slice the failures by AZ, LB node, backend host, client version and resolver; one bad backend out of fifty conveniently gives you about 2%.

Because I can't reproduce on demand, I build observation: continuous probes from several vantage points including a mobile network, client-side error telemetry with request IDs, temporary verbose sampling, and a ring-buffer tcpdump filtered on SYN/RST so a capture exists when it next fires.

My top hypotheses for 'works when I test it' are an idle-timeout mismatch — LB or NAT closing an idle connection the client's pool still thinks is alive, so you get a RST on reuse — plus health-check flapping, conntrack or ephemeral-port exhaustion, listen-backlog overflows, and one bad DNS A record. I'd verify the fix by watching the prober's residual rate, and leave behind a client-side error SLI.
