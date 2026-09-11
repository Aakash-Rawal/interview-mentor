---
id: pe-lnx-02
domain: pe
topic: linux
difficulty: easy
tags: [load, cpu, top]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Load average on a 4-core box is 12. Is that bad? What does load average actually measure on Linux, and what would you look at next?

## What interviewers look for
- Immediately reframes load as runnable + uninterruptible, not CPU utilisation
- Normalises against core count and asks about the 1/5/15 trend rather than a single number
- Proposes an ordered elimination: CPU-bound vs I/O-blocked vs lock/NFS hang vs steal
- Names the exact column in each tool's output they're reading, not just the tool name
- Treats 'is it bad?' as a question about SLOs and latency, not the number itself

## Strong answer covers
1. Explains Linux load = exponentially-damped moving average of tasks in TASK_RUNNING plus TASK_UNINTERRUPTIBLE (D state), unlike traditional Unix which counts only runnable — so load 12 on 4 cores can be entirely disk/NFS wait with idle CPUs
2. Compares 1/5/15-minute values to see if the event is rising, decaying, or steady, and divides by `nproc` (12/4 = 3x) for a per-core saturation sense
3. `vmstat 1`: reads r (runnable, compare to core count) vs b (blocked on I/O), plus si/so for swap and the us/sy/id/wa split; wa high with low r points at storage
4. `mpstat -P ALL 1` to see whether one core is hot or all are, high %sys indicating syscall/spinlock storms, and %steal indicating a noisy hypervisor neighbour
5. `ps -eo state,pid,wchan:32,cmd | awk '$1 ~ /^D/'` to enumerate D-state tasks and `cat /proc/<pid>/stack` or wchan to see which kernel path they're stuck in (nfs, blk, rwsem)
6. `iostat -xz 1` for await, aqu-sz and %util per device to confirm storage saturation; `pidstat -d 1` to attribute I/O to a process
7. Mentions PSI (`/proc/pressure/{cpu,io,memory}`) as a cleaner saturation signal than load average, and that the answer to 'is it bad' comes from latency/error SLOs, not the number
8. Notes traps: load includes kernel threads, a hung NFS mount pins load high forever, and container CPU limits (cfs throttling, `/sys/fs/cgroup/cpu.stat` nr_throttled) cause latency without high host load

## Follow-ups
- Load is 12, vmstat shows r=1, b=11 and iostat shows near-zero I/O. What's left?
- How would you distinguish CPU throttling in a container from genuine CPU saturation on the host?
- %steal is 30%. What do you do, and what can you actually control?
- Why might PSI be a better alerting signal than load average across a heterogeneous fleet?

## Sample answer
Not necessarily bad — load on Linux isn't CPU utilisation. It counts tasks that are runnable *and* tasks in uninterruptible sleep, which is usually disk or NFS I/O. So 12 on 4 cores could be four CPU-bound threads and eight processes blocked on a slow volume, with CPUs mostly idle. First I'd look at the 1/5/15 trend to see if it's rising or decaying, then `vmstat 1`: if r is around 12 and wa is near zero, we're genuinely CPU-saturated; if b is high and wa is large, it's storage. `mpstat -P ALL 1` tells me whether it's one hot core or all of them, whether %sys is abnormal, and whether %steal means a noisy neighbour on the hypervisor. If it's I/O I go to `iostat -xz 1` for await and %util per device and `pidstat -d 1` to attribute it. I'd also list D-state tasks with `ps -eo state,pid,wchan,cmd` and read `/proc/<pid>/stack` — a hung NFS mount will hold load high indefinitely with no real work happening. Honestly I'd rather alert on PSI, `/proc/pressure/io` and `cpu`, because it's a direct saturation measure and comparable across machines with different core counts. And the real question is whether latency and error SLOs are affected.
