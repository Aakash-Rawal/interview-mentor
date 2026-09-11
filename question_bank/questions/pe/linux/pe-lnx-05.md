---
id: pe-lnx-05
domain: pe
topic: linux
difficulty: hard
tags: [performance, cpu, perf]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A Python service is pegging one CPU core at 100% while the others are idle, and latency is up. Diagnose without restarting it.

## What interviewers look for
- Goes thread-level first to prove it's one thread, not just one process
- Uses a profiler that gives Python-level stacks, not only C-level symbols
- Explicitly weighs invasiveness — knows strace/gdb pause the process and says so before using them
- Separates userland spin from syscall storm from GC/regex/lock pathology using evidence
- Connects the CPython threading model to why one core saturates and what the fix looks like

## Strong answer covers
1. `top -H -p <pid>` or `ps -L -o pid,tid,pcpu,stat,comm -p <pid>` to find the hot TID, and `pidstat -t -p <pid> 1` to confirm it's one thread at ~100% while others idle
2. `py-spy top --pid <pid>` and `py-spy dump --pid <pid>` for Python-level stacks without stopping the process (py-spy reads memory; note --nonblocking trade-off), or `perf top -p <pid>` / `perf record -F 99 -g -p <pid>` for C-level and a flamegraph
3. `strace -c -f -p <pid>` for a short window to distinguish a syscall storm (high %sys) from pure userland spin (high %usr), and `mpstat -P ALL 1` / `pidstat 1` to read the us/sy split
4. Explains the GIL: CPython runs one bytecode-executing thread at a time, so a CPU-bound thread saturates exactly one core and starves other threads; `sys.setswitchinterval`, and that C extensions releasing the GIL behave differently
5. Differential diagnosis: infinite/busy loop, pathological regex backtracking, O(n^2) on a grown dataset, JSON/serialisation hot path, GC pressure (gc stats, large object graphs), a spin-wait on a lock, or a poll loop with zero timeout
6. States invasiveness and blast radius: py-spy is read-only-ish and safe; `strace` can slow the target several-fold; `gdb -p` stops it entirely — so run those briefly, on one replica, ideally after taking it out of the load balancer
7. Correlates with recent change: deploy diff, a new input shape, request rate on the endpoint that got slow, and `/proc/<pid>/status` voluntary vs nonvoluntary_ctxt_switches
8. Fixes: remove the box from rotation, capture profile, then fix the hot path; scale out with multiple worker processes (gunicorn/uvicorn workers = cores), move CPU work to a C extension/numpy/subprocess pool, or offload to a queue; add continuous profiling so this is visible next time

## Follow-ups
- py-spy shows the top frame is in a C extension with no Python frames. What now?
- The thread is at 100% but %sys is 90%. How does that change your hypothesis?
- How would you capture this evidence safely on a box that's still serving live traffic?
- What would you add to the service so the next occurrence is diagnosed from dashboards instead of SSH?

## Sample answer
I'd first prove it's one thread: `top -H -p <pid>` or `pidstat -t -p <pid> 1` to get the hot TID. Then I want a Python-level stack, so `py-spy top --pid <pid>` and a couple of `py-spy dump`s — that gives me the actual function without stopping the process, which matters since it's still serving. In parallel I'd look at the us/sy split in `mpstat`/`pidstat`: mostly user time points at a busy loop, pathological regex backtracking, an accidental O(n²) on data that's grown, or GC churn; high system time points at a syscall storm, and I'd confirm with a 10-second `strace -c -f -p <pid>`, saying up front that strace slows the target so I'd do it briefly and ideally after draining the host from the LB. Structurally, CPython's GIL means one bytecode thread runs at a time, so a CPU-bound thread saturates exactly one core and starves the rest of the process — that's consistent with what we're seeing and also explains the latency hit on other requests. If I want a flamegraph I'd add `perf record -F 99 -g -p <pid>`. The fix depends on the stack: fix the hot path, or run multiple worker processes rather than threads, or push the CPU work into a C extension or a worker queue. Longer term I'd want continuous profiling so we don't need SSH next time.
