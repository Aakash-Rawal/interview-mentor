---
id: pe-lnx-08
domain: pe
topic: linux
difficulty: medium
tags: [boot, systemd]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A host comes back from reboot but the app service is not running. Walk through how you'd find out why using systemd tooling.

## What interviewers look for
- Follows the systemd chain: state → logs → dependencies → unit file, without guessing
- Distinguishes 'disabled' from 'failed' from 'never started because a dependency failed'
- Reads exit codes and Restart/StartLimit semantics correctly
- Knows the boot-ordering traps (network-online vs network, remote mounts, DNS)
- Makes the change reversibly and verifies by actually rebooting or simulating

## Strong answer covers
1. `systemctl status <unit>` first: reads Loaded (enabled/disabled/masked, vendor preset), Active state and substate, Main PID, exit code/signal, and the last few log lines
2. `systemctl is-enabled <unit>` — a common cause is simply never enabled, so it ran only because someone started it manually; `systemctl enable --now` fixes it; also check for `masked`
3. `journalctl -u <unit> -b` (and `-b -1` for the previous boot, requires persistent journal via /var/log/journal or Storage=persistent) to see the actual failure; `journalctl -b -p err` for system-wide boot errors
4. Exit-code reading: status=1/FAILURE vs 203/EXEC (binary missing/not executable), 200/CHDIR, 226/NAMESPACE, 217/USER (missing user), signal=SIGKILL as OOM or TimeoutStartSec; ExecStartPre failures abort start
5. Dependency and ordering: `systemctl list-dependencies <unit>`, `systemctl list-units --failed`, `systemd-analyze critical-chain <unit>`, `systemd-analyze blame`; classic bug is After=network.target instead of network-online.target plus the corresponding Wants=, or binding to an IP before the interface is up, or a NFS/iSCSI mount or /var not ready
6. Restart semantics: Restart=on-failure vs always, RestartSec, StartLimitIntervalSec/StartLimitBurst — a crash-looping service hits the start limit and enters 'failed (start-limit-hit)' and stays down; recover with `systemctl reset-failed <unit>`
7. Checks the unit file for drift: `systemctl cat <unit>` to see the merged unit plus drop-ins, `systemd-delta` for overrides, and always `systemctl daemon-reload` after editing or systemd uses the stale unit
8. Also checks environment causes: EnvironmentFile missing, ConditionPathExists/ConditionFileNotEmpty silently skipping the unit ('condition failed' shows as inactive, not failed), WorkingDirectory missing, User/Group deleted, SELinux denial, filesystem not mounted
9. Fix quality: use `systemctl edit <unit>` for a drop-in rather than editing the vendor file, keep it reversible, verify with a real reboot or `systemctl isolate`/container test, and push the corrected unit through config management with a fleet-wide check that all hosts have it enabled and active

## Follow-ups
- Status says 'inactive (dead)' with no log lines at all. What does that tell you?
- The service works when you start it by hand after boot but fails at boot. What's your prime suspect and how do you prove it?
- How do you get logs from the boot *before* last, and what has to be configured for that?
- The unit is crash-looping and systemd has given up. What exactly stopped it and how do you reset it?

## Sample answer
I'd start with `systemctl status <unit>` and read three things: whether it's Loaded enabled or disabled or masked, the Active state, and the exit code or signal. A surprising number of these are simply 'disabled' — the service was only ever started by hand, so `systemctl is-enabled` answers it and `systemctl enable --now` fixes it. If it's failed, I go to `journalctl -u <unit> -b` for this boot, and `-b -1` for the previous one if the journal is persistent. Exit codes are informative: 203/EXEC means the binary is missing or not executable, 217/USER means the service user doesn't exist, SIGKILL usually means OOM or a TimeoutStartSec. If it never even tried, I look at ordering: `systemd-analyze critical-chain <unit>`, `systemctl list-dependencies`, and `systemctl --failed`. The classic boot-only bug is After=network.target when you actually need network-online.target with the matching Wants=, or binding to an IP before the interface has it, or a remote mount not ready. Also possible is a Condition= that silently skipped the unit, which shows as inactive rather than failed. And if it crash-looped, StartLimitBurst will have latched it into start-limit-hit, needing `systemctl reset-failed`. I'd fix it with `systemctl edit` as a drop-in so it's reversible, `daemon-reload`, then actually reboot a canary to verify, and ship the unit through config management with a fleet check that it's enabled and active everywhere.
