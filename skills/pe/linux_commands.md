# Linux Commands & When To Use Each (PE / SRE)

## Brendan Gregg 60-second checklist
First 60 seconds on a sick box, in order:
1. `uptime` — load averages (1/5/15 min trend).
2. `dmesg | tail` — recent kernel errors (OOM killer, drops).
3. `vmstat 1` — `r` (runnable), `b` (blocked), `si/so` (swapping).
4. `mpstat -P ALL 1` — per-CPU balance; one hot CPU = single-threaded bottleneck.
5. `pidstat 1` — per-process CPU over time.
6. `iostat -xz 1` — `%util`, `await`; disk saturation.
7. `free -m` — memory + cache; near-zero available + swap = pressure.
8. `sar -n DEV 1` — network throughput vs NIC limit.
9. `sar -n TCP,ETCP 1` — retransmits, resets.
10. `top` / `htop` — overall picture.

## Command → symptom map
| Symptom | Reach for | Why |
|---|---|---|
| High load, low CPU | `iostat`, `vmstat` | likely I/O or run-queue blocking |
| One core pinned | `mpstat -P ALL` | single-threaded hot path |
| Process eating RAM | `pidstat -r`, `smem` | RSS vs shared |
| "Disk full" but `df` ok | `df -i` | inode exhaustion |
| Slow network | `ss -s`, `sar -n DEV` | sockets, throughput |
| Mystery latency | `strace -p`, `perf top` | syscalls / on-CPU profiling |
| Connection refused | `ss -tlnp` | is anything listening? |

## Pathological behaviours (define these crisply)
- **Thrashing** — system spends more time swapping pages than doing work.
- **Thundering herd** — many clients wake/retry simultaneously, overwhelming a recovering service.
- **OOM killer** — kernel kills the highest-badness-score process when memory is exhausted.
- **Retransmit storm** — packet loss causes TCP retransmits that worsen congestion.

## Behaviour
Characterise before acting. Confirm safety before any destructive command.
Prefer the simplest safe fix; frame prevention fleet-wide.
