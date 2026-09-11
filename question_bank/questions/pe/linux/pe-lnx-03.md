---
id: pe-lnx-03
domain: pe
topic: linux
difficulty: medium
tags: [memory, oom]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A process was killed overnight with no application log. How do you confirm it was the OOM killer, understand why it chose that process, and prevent it?

## What interviewers look for
- Goes to kernel logs before application logs and knows what the OOM report contains
- Distinguishes global OOM from cgroup/container OOM and checks both
- Reads the victim-selection logic rather than saying 'it killed the biggest process'
- Separates leak from legitimate growth from over-commit misconfiguration before proposing a fix
- Prevention is layered: limits, oom_score_adj, alerting on the right metric, fleet rollout

## Strong answer covers
1. `dmesg -T | grep -i -E 'oom|killed process'` or `journalctl -k --since yesterday` to find 'Out of memory: Killed process <pid> (<name>) total-vm:..., anon-rss:..., file-rss:...' plus the preceding task list and `oom_score` column
2. Also checks `journalctl -u <unit>` for systemd reporting the unit as killed, and exit status 137 / SIGKILL, plus `systemctl show <unit> -p NRestarts` and `memory.events` oom_kill counter
3. Explains victim selection: oom_score is driven by RSS plus swap plus page tables, scaled, adjusted by `/proc/<pid>/oom_score_adj` (-1000..1000); -1000 makes a task exempt; the kernel kills the process that frees the most memory, not necessarily the culprit
4. Distinguishes global OOM (whole-host memory exhausted, check `free -m` available, `/proc/meminfo`, slab via `slabtop`) from cgroup OOM (memory.max / memory.high hit, only that container's tasks are candidates, `memory.events` and `memory.pressure`)
5. Investigates cause: is it a leak (RSS trending up over days in historical metrics, `pmap -x`, heap profiler, jemalloc/gdb), a load spike, a page-cache vs anon confusion, THP bloat, or a missing memory limit/over-commit setting (`vm.overcommit_memory`, `vm.swappiness`)
6. Checks whether swap was available and whether the box was thrashing beforehand: `vmstat 1` si/so, `sar -B`/`sar -r` historical data, PSI `/proc/pressure/memory` avg10/avg60
7. Prevention: set cgroup memory.max with headroom plus memory.high for graceful throttling, `OOMPolicy`/`MemoryMax` in the systemd unit, `oom_score_adj` to protect sshd/monitoring agents and bias toward the workload, alert on RSS trend and PSI rather than on the kill itself, add a heap dump on threshold
8. Notes data-preservation/evidence: capture dmesg, the per-process memory table from the OOM report, and metrics before restarting; consider `systemd-coredump` or a core for post-mortem

## Follow-ups
- The OOM report shows the killed process had only 400MB RSS on a 64GB host. How is that possible?
- How would you tell a genuine leak from fragmentation or page-cache growth?
- What's the difference between memory.high and memory.max, and when would you use each?
- Your fix is to raise the limit. How do you decide the number, and what's the risk?

## Sample answer
First stop is the kernel ring buffer, not the app log: `dmesg -T | grep -i 'killed process'` or `journalctl -k --since yesterday`. The OOM report gives me the victim's pid, name, total-vm and anon-rss, plus the full task table with each process's oom_score — that tells me who was actually consuming memory versus who got killed. I'd also check systemd: an exit status of 137 and the unit's `memory.events` oom_kill counter tell me whether this was a cgroup OOM inside a container limit or a global host OOM. That distinction matters, because a cgroup OOM only considers tasks in that cgroup. Selection is by oom_score — roughly RSS plus swap, adjusted by oom_score_adj — so the kernel kills whoever frees the most memory, which is often the victim rather than the cause. Then I'd figure out why: historical RSS trend for a leak, `/proc/pressure/memory` and vmstat si/so for prior thrashing, slabtop and meminfo if it's kernel-side. Prevention is layered: a memory.max with headroom plus memory.high so the workload throttles before it's killed, oom_score_adj -900 on sshd and the monitoring agent so we keep access, alerting on RSS trend and memory PSI rather than on the kill itself, and rolling that config out through config management so all hosts get it.
