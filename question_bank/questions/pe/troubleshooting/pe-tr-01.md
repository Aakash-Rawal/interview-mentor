---
id: pe-tr-01
domain: pe
topic: troubleshooting
difficulty: hard
tags: [latency, methodology, use]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
One host in a fleet shows 10x p99 latency versus its peers. Same code, same config. How do you find why?

## What interviewers look for
- Characterises before touching: when it started, which requests, whether the host is actually taking equal traffic
- Uses a healthy peer as the control and diffs systematically rather than guessing a cause
- Walks layers with named tools (USE method: utilisation, saturation, errors per resource)
- Captures evidence before remediating, and considers draining the host from the LB as a safe reversible mitigation
- Ends fleet-wide: outlier detection so a human doesn't have to notice next time

## Strong answer covers
1. Characterise first: since when, all endpoints or one, p99 only or p50 too (tail-only points at GC/lock/IRQ/one slow dependency; both bad points at saturation), and whether the host's request rate/mix differs from peers (LB hash imbalance, a hot shard or hot cache key resident there, it being a leader/coordinator)
2. Verify the 'same code, same config' claim rather than accepting it: package/image version, kernel and microcode, config-management dry run or checksum diff, sysctl diff, uptime (a recently restarted host has cold caches/JIT), feature-flag or canary cohort membership
3. CPU: `mpstat -P ALL 1` for %steal (noisy neighbour) and for a single pegged core, `top -H`, frequency/thermal throttling (`turbostat`, `cpupower frequency-info`, `/proc/cpuinfo` MHz), `cat /proc/interrupts` and IRQ affinity / RPS-RSS imbalance pinning softirq to one CPU
4. Memory: free/available vs peers, swap in-out via `vmstat 1` (si/so), THP and khugepaged/compaction stalls, NUMA imbalance (`numastat`), page cache size, cgroup memory pressure and `memory.stat`/PSI (`/proc/pressure/*`)
5. Disk: `iostat -x 1` await/aqu-sz/%util, degraded RAID or a failing device retrying (`dmesg`, `smartctl`, mdstat), filesystem full or fsync latency; Network: `ethtool -S` drops/errors, `ethtool` negotiated speed/duplex (a 1G-negotiated link in a 10G fleet), `ip -s link`, `ss -ti` retransmits, conntrack table, `netstat -s`/`nstat` for listen overflows
6. Process level: thread dump / `jstack` or `perf top -p`, GC logs and pause distribution, lock contention, fd count vs limit, and a `perf record` + flame graph comparison against the healthy peer
7. Data preservation and safe mitigation order: snapshot logs, `dmesg`, thread dump, `perf`, connection table first; then drain the host from the load balancer (reversible, restores user latency immediately) and keep it out of service for forensics rather than rebooting it away
8. Fleet-wide prevention: per-host outlier alerting (host p99 vs fleet median, %steal, NIC errors, negotiated link speed), automated drain-on-outlier, hardware health feed into the scheduler, and a ticket to the infra/hardware owner if it is a noisy neighbour or bad NIC

## Follow-ups
- `mpstat` shows 35% steal on this host and 2% on peers. What do you do in the next ten minutes, and what do you tell the platform team?
- Every host metric looks identical to the healthy peer. Where do you look next?
- The flame graph shows most time in kernel softirq on CPU0. Explain what's likely happening and how you'd confirm and fix it.
- Design the alert that would have caught this in five minutes without paging on every noisy host in a 5,000-node fleet.

## Sample answer
First I'd characterise: since when, is it all endpoints or one, and is p50 also bad or only the tail? Tail-only suggests GC, a lock, IRQ imbalance or one slow dependency; both bad suggests saturation. I'd also check the host isn't simply getting different work — LB hash imbalance, a hot key or hot shard living there, or it being the shard leader.

Then I treat a healthy peer as a control and diff everything, because 'same code, same config' is a claim to verify: package version, kernel, sysctls, config-management dry run, uptime for cold caches. Then USE per resource: `mpstat -P ALL` for steal and single-core pegging, `/proc/interrupts` for IRQ affinity, `vmstat` for swap, `iostat -x` for await, `dmesg`/`smartctl` for a failing disk, `ethtool -S` and negotiated link speed for a 1G-negotiated NIC, `ss -ti` for retransmits. In-process: thread dump, GC log, and a `perf` flame graph diffed against the peer.

Before I fix anything I snapshot logs, dmesg, thread dump and connection table, then drain the host from the LB — reversible, fixes user latency now, keeps the box for forensics. Fleet-wide I'd add per-host outlier alerting on p99 versus fleet median plus steal, NIC errors and link speed, and auto-drain on outlier.
