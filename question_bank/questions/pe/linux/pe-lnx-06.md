---
id: pe-lnx-06
domain: pe
topic: linux
difficulty: easy
tags: [filesystems, permissions]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A cron job runs fine manually but fails when cron runs it. List the likely causes and how you'd pin each one down.

## What interviewers look for
- Treats it as an environment-difference problem and enumerates the dimensions systematically
- Knows where cron's own output goes and how to capture the job's output before guessing
- Reproduces the failure deliberately rather than 'adding absolute paths and hoping'
- Mentions locking/overlap, timezone/DST, and %-escaping — the things most candidates miss
- Ends with a durable pattern: wrapper script, logging, exit-code alerting, or moving to a timer

## Strong answer covers
1. Capture the evidence first: redirect in crontab `>> /var/log/job.log 2>&1`, or check MAILTO/local mail; cron's own log via `journalctl -u cron`/`crond` or /var/log/cron shows the command line it ran and the exit status
2. Environment: cron gives a minimal env — typically only HOME, LOGNAME, PATH=/usr/bin:/bin, SHELL=/bin/sh — so no .bashrc/.bash_profile, no virtualenv, no language managers (rbenv/nvm/pyenv), no proxy vars, no AWS_* or KRB5 credentials
3. Reproduce deterministically with `env -i /bin/sh -c 'cd /; /path/to/cmd'` or `env -i HOME=/home/svc PATH=/usr/bin:/bin ...`, and compare with `env` captured inside a cron run
4. Working directory: cron starts in $HOME, so relative paths, relative config includes, and `./script` break; fix with absolute paths or an explicit `cd`
5. Shell differences: /bin/sh is dash on Debian-family, so bashisms ([[ ]], arrays, pipefail, source) fail; set SHELL=/bin/bash or use a `#!/bin/bash` wrapper script
6. User and permissions: system crontab (/etc/crontab, /etc/cron.d) has a user field, per-user crontabs don't; check file ownership, umask, sudoers requiring a TTY (`requiretty`), SELinux/AppArmor denials in audit.log
7. Cron-specific syntax traps: `%` must be escaped as `\%` in crontabs, a missing trailing newline in some crond implementations, and no terminal so anything expecting a TTY or interactive input fails
8. Timing issues: overlapping runs without a lock (use `flock -n /var/lock/job.lock`), timezone/DST skips and double-runs, the job depending on another service not yet up, and resource limits differing from an interactive shell
9. Durable fix: a wrapper script with `set -euo pipefail`, explicit env sourcing, absolute paths, flock, structured logging and exit-code propagation; or move to a systemd timer for logging, dependencies, and Restart semantics — plus alerting on missed/failed runs

## Follow-ups
- The job succeeds under `env -i` too. What else differs between your shell and cron?
- The job sometimes runs twice and corrupts state. How do you make it safe?
- Why might you move this to a systemd timer, and what do you gain and lose?
- How would you detect across 5,000 hosts that a nightly job silently stopped running?

## Sample answer
Nine times out of ten it's environment. Cron runs with a minimal env — basically HOME, LOGNAME, a short PATH and SHELL=/bin/sh — and it doesn't source .bashrc or .bash_profile, so virtualenvs, nvm/pyenv shims, proxy variables and credentials that my interactive shell has are all absent. It also starts in $HOME, so relative paths break, and /bin/sh is dash on Debian, so bashisms fail. First thing I'd do is capture output rather than theorise: add `>> /var/log/job.log 2>&1` to the crontab entry, and check cron's own log via journalctl or /var/log/cron to see the exact command line and exit status. Then reproduce deliberately: `env -i /bin/sh -c '/path/to/cmd'` from / and see it fail the same way, and dump `env` from inside a cron run to diff against my shell. I'd also check the user — system crontabs in /etc/cron.d have a user field, per-user ones don't — plus file permissions, umask, a sudoers requiretty, and SELinux denials in audit.log. Subtle ones: unescaped `%` in the crontab, and overlapping runs with no lock. The durable fix is a wrapper script with set -euo pipefail, absolute paths, explicit env, flock for mutual exclusion, and logging — or a systemd timer, which gives me journal logging, dependency ordering and failure alerting for free.
