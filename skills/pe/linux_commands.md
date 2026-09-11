# Linux Internals & Commands — Production Engineering / SRE

## What this interview actually tests
Whether you can **characterise** a sick box quickly, pick the right tool for the symptom,
**read the output correctly**, and fix it without destroying evidence or data. Interviewers
role-play the machine: you say the command, they give you output, you interpret. Scored on:
discovery questions, systematic elimination, command choice, reading output, data
preservation, fix quality, and fleet-wide prevention.

## The 60-second checklist (Brendan Gregg) — run it in this order
```
uptime                  load avg over 1/5/15 min: rising, falling, spiky?
dmesg -T | tail         OOM kills, disk errors, NIC resets, segfaults
vmstat 1                r (runnable) vs b (blocked); si/so (swap!); us/sy/id/wa
mpstat -P ALL 1         one hot CPU? high %sys? %steal (noisy VM neighbour)?
pidstat 1               which process; -d for disk, -r for memory
iostat -xz 1            await, %util, r/s w/s, queue depth per device
free -m                 available vs free; buff/cache is reclaimable
sar -n DEV 1            NIC throughput, errors, drops
sar -n TCP,ETCP 1       retransmits, active/passive opens
top / htop              sanity check; press 1 (per-CPU), H (threads), M/P (sort)
```
Say the *reason* for each command as you run it. "vmstat first because it shows CPU,
memory, and I/O wait on one line."

## Symptom → first tools
| Symptom | Look at | Key signals |
|---|---|---|
| high load, CPU idle | `vmstat` b column, `ps -eo state,pid,cmd \| grep '^D'` | I/O wait, D-state processes, NFS hang |
| high %sys | `perf top`, `strace -c -p`, `pidstat -w` | syscall storm, context switches, spinlocks |
| memory pressure | `free -m`, `vmstat` si/so, `dmesg` OOM, `/proc/meminfo` | swapping, OOM kills, slab/THP growth |
| disk full | `df -h`, `df -i`, `du -xh --max-depth=1 /`, `lsof +L1` | inodes, deleted-but-open files |
| slow disk | `iostat -xz 1`, `iotop`, `blktrace` | await ≫ svctm, %util ~100, queue depth |
| network slow | `ss -s`, `ss -tin`, `sar -n DEV,TCP,ETCP`, `ethtool -S`, `tcpdump` | retransmits, drops, NIC errors, buffer limits |
| process hung | `cat /proc/<pid>/stack`, `strace -p`, `gdb -p` / `py-spy dump` | what syscall it's blocked in |
| service down | `systemctl status`, `journalctl -u X -b`, `ss -ltnp` | exit code, listening?, dependencies |
| can't connect | `ss -ltnp`, `iptables -S`/`nft list ruleset`, `tcpdump`, `curl -v` | listening address, firewall, SYN with no SYN-ACK |

## Facts worth having cold
- **Load average** counts runnable **and** uninterruptible (D) tasks. Load 12 on 4 cores can
  be pure I/O wait. Compare to core count; check `vmstat` r vs b.
- **free vs available**: `available` is what matters; page cache is reclaimable.
- **OOM killer** picks by `oom_score` (RSS + adjustments via `oom_score_adj`); cgroup
  limits (`memory.max`) trigger it per container. Confirm with `dmesg -T | grep -i oom`.
- **Zombie**: exited, parent hasn't `wait()`ed; only a PID slot. Fix the parent. **Orphan**:
  parent died; reparented to init/subreaper. `kill -9` cannot kill D-state or zombies.
- **Signals**: SIGTERM (15) polite, SIGKILL (9) unstoppable and uncatchable, SIGHUP often
  "reload config", SIGCHLD to parent on child exit.
- **File descriptors**: `ulimit -n`, `/proc/<pid>/limits`, `ls /proc/<pid>/fd | wc -l`,
  `lsof -p`. "Too many open files" = fd leak or limit too low.
- **Deleted-but-open file** still consumes space: `lsof +L1`; truncate via
  `: > /proc/<pid>/fd/<n>` if you must free space without a restart.
- **Inodes**: `df -i`; millions of tiny files exhaust inodes with space "free".
- **TCP states**: `ss -tan state time-wait | wc -l`; ephemeral port exhaustion →
  EADDRNOTAVAIL; `net.ipv4.ip_local_port_range`, `tcp_tw_reuse`.
- **Listen backlog**: `ss -ltn` Recv-Q vs Send-Q; overflow shows in `nstat -az TcpExtListenOverflows`.
- **THP / swap / NUMA** can each explain "random" latency; `numastat`, `cat /sys/kernel/mm/transparent_hugepage/enabled`.
- **systemd**: `systemctl status/restart/enable`, `journalctl -u X -b --since "10 min ago"`,
  unit ordering (`After=`, `Requires=`), `Restart=`, `StartLimitBurst`, `daemon-reload` after edits.
- **cron** failures: different env/PATH/user, relative paths, output discarded.
  Reproduce with `env -i /bin/sh -c 'cmd'`.
- **/proc** is the truth: `/proc/<pid>/{status,fd,stack,io,limits,cgroup}`, `/proc/meminfo`,
  `/proc/net/*`, `/proc/pressure/*` (PSI).

## Data-preservation reflexes (say these out loud)
- "Before I restart anything, I'll capture `dmesg`, the process stack, and `ss -tanp` so we
  have evidence."
- Never `rm` logs to free space; `truncate`/`logrotate`/compress. Never `rm -rf` on a path
  you haven't `ls`'d.
- Prefer read-only diagnostics first; escalate to invasive (`strace`, `gdb`, restart) with a
  stated reason and blast-radius check.
- Take a copy of config before editing; make the change reversible.

## Fix quality → fleet-wide prevention
Simplest safe fix first (restart the leaking process), then root cause, then: alerting
threshold, resource limit, log rotation, kernel tunable in config management, runbook.
Always end with "how do I make sure this can't happen on the other 5,000 hosts?"

## Common mistakes
- Reaching for `top` and staring instead of running the checklist.
- Misreading `free` (panicking about page cache) or load average (ignoring I/O wait).
- Restarting the service first and losing the evidence.
- Quoting a tunable without saying what it does or how to verify it took effect.
- Forgetting `df -i` and `lsof +L1` on a "disk full" that isn't.

## Practice prompts
- `df` says 40% free but writes fail. / Load 30 on 8 cores, CPU 10% busy.
- p99 latency doubled on one host in a pool of 50 after a kernel upgrade.
- A daemon has 65k fds open and climbing. / `ps` shows 3,000 zombies.
- Service listens on 127.0.0.1 but the LB health check fails from outside.
- Every night at 02:00 the box swaps for 10 minutes.
