---
id: pe-lnx-04
domain: pe
topic: linux
difficulty: medium
tags: [processes, signals, zombie]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Explain the difference between a zombie and an orphan process. `ps` shows thousands of zombies — what's happening and how do you fix it?

## What interviewers look for
- Defines both states precisely in terms of the process table and wait() semantics
- Knows that signalling a zombie is meaningless and says why
- Traces from symptom to the offending parent rather than treating zombies as the problem
- Connects to real-world causes: PID 1 in containers, broken SIGCHLD handlers, fork bombs of short-lived children
- Recognises the real risk is PID exhaustion, and quantifies it

## Strong answer covers
1. Zombie (EXIT_ZOMBIE, ps state Z, 'defunct'): the process has exited and released memory/fds, but the parent hasn't called wait()/waitpid(), so the kernel keeps the task_struct holding exit status, pid, and rusage
2. Orphan: the parent died first, so the child is reparented to PID 1 (init) or the nearest subreaper (`prctl(PR_SET_CHILD_SUBREAPER)`), which reaps it — orphans are normal and harmless; an orphaned zombie gets cleaned automatically
3. `kill -9` on a zombie is a no-op — there's no process left to signal; you must make the parent reap or kill the parent, which reparents the zombies to init and they vanish
4. Finds the culprit: `ps -eo pid,ppid,state,cmd | awk '$3 ~ /Z/'` then group by PPID, or `ps -ef | grep defunct`; inspect the parent with `strace -p <ppid>` (is it blocked in a syscall and never returning to wait?), `cat /proc/<ppid>/stack`, `/proc/<ppid>/status` for thread count
5. Root causes: parent missing a SIGCHLD handler or waitpid loop, SIGCHLD set to SIG_IGN incorrectly vs correctly, parent stuck in a blocking call, a container whose PID 1 is an app rather than a real init (use `--init`/tini/dumb-init, or systemd with the right KillMode)
6. Real impact: zombies consume a PID slot and a small kernel struct; thousands approach `/proc/sys/kernel/pid_max` (often 32768 or 4194304) and can cause fork() failures — check `cat /proc/sys/kernel/pid_max`, `ps -e | wc -l`, and cgroup `pids.max`/`pids.current`
7. Fix sequence: capture evidence (ps snapshot, parent stack, strace) → SIGCHLD/HUP or restart the parent as the quick fix → patch the parent to reap properly or add a subreaper init → alert on zombie count and pids.current fleet-wide

## Follow-ups
- How does setting SIGCHLD to SIG_IGN change the behaviour, and why is that a footgun?
- Inside a container, PID 1 is the application itself. What breaks and how do you fix it?
- What's the difference between a zombie and a D-state process from an operational standpoint?
- How many zombies before this is an actual outage, and what alert would you write?

## Sample answer
A zombie has already exited — memory and fds are released — but the parent hasn't called wait(), so the kernel keeps a task_struct around holding the exit status and rusage. It's just a PID slot. An orphan is the opposite: the parent died first, so the child is reparented to PID 1 or the nearest subreaper, which reaps it. Orphans are normal; zombies that accumulate mean a parent that isn't reaping. Thousands of zombies tells me one parent is broken, so I'd run `ps -eo pid,ppid,state,cmd | awk '$3 ~ /Z/'` and group by PPID to identify it. Then I'd look at that parent: `strace -p <ppid>` and `/proc/<ppid>/stack` — typically it's blocked in a syscall and never returns to its waitpid loop, or it has no SIGCHLD handler at all. Killing zombies with -9 does nothing; there's no process to signal. The quick fix is to restart the parent, which reparents the zombies to init and they disappear. In a container the classic cause is PID 1 being the app, which has no reaping duty; fix is a real init like tini or `--init`. The actual risk is PID exhaustion — check pid_max and cgroup pids.current — so I'd alert on zombie count and PID usage, and file the parent bug.
