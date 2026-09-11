---
id: pe-tr-05
domain: pe
topic: troubleshooting
difficulty: easy
tags: [methodology, disk]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A disk on a production host is 98% full and growing. What do you do in the next five minutes, and what do you do next week?

## What interviewers look for
- Acts fast but never deletes data they can't explain; prefers rotate/compress/truncate/move over rm
- Knows the traps: deleted-but-open files, inode exhaustion, filesystem reserve, WAL/replication
- Asks what is growing and why, not just what is big
- Considers service impact of a full disk (write errors, read-only remount) and checks the rest of the fleet
- Prevention is rate-based and structural: logrotate, retention, separate partitions, time-to-full alerting

## Strong answer covers
1. Assess impact and rate first: `df -h` and `df -i` (inodes can exhaust with space free), how fast it's growing (`df` sampled, or the monitoring graph) and therefore minutes-to-full; is the service already erroring on writes, and is there risk of a read-only remount or DB shutdown
2. Locate the growth, not just the size: `du -xh --max-depth=1 /` walking down (`-x` to stay on one filesystem), `find / -xdev -size +1G -mtime -1`, and `lsof +L1` for deleted-but-still-open files where space is only released when the holder closes the fd or you `truncate -s 0 /proc/PID/fd/N`
3. Safe first actions: `logrotate -f` on the offending config, gzip old logs, truncate rather than `rm` a file an active process holds (rm frees nothing until the fd closes), move data to another volume, delete clearly reclaimable artifacts (old package cache, old container images/layers via `docker system prune`, core dumps, journal via `journalctl --vacuum-size=1G`); explicitly never `rm -rf` anything you can't explain
4. Know the emergency levers and their cost: the ext4 5% root reserve (`tune2fs -m 1` buys space), a pre-created ballast file to delete, and expanding the volume/LVM online (`lvextend` + `resize2fs`/`xfs_growfs`) — the cleanest fix if the platform allows it
5. Ask why it's growing: debug/trace log level left on after an incident, a log-shipper stuck so local buffers grow, a retry loop writing stack traces, tmp files never cleaned, an unbounded cache, DB-specific causes such as PostgreSQL WAL retained by an inactive replication slot or a failing `archive_command`, or table/index bloat — deleting WAL by hand breaks recoverability and can destroy the cluster
6. Preserve evidence and coordinate: keep or copy a sample of what you delete, snapshot before destructive action where possible, and confirm with the data owner before touching database, audit or compliance-retained files
7. Check the blast radius fleet-wide: the same growth is probably on all peers — query the fleet for hosts above 85% and for time-to-full, and drain/handle them before they page one by one
8. Next week: logrotate with size+age and compression, explicit retention policy, ship logs off-box so local disk isn't the system of record, separate partitions for logs/data/root so a log flood can't take down the service, alerts on rate of change and projected time-to-full (e.g. Prometheus `predict_linear(node_filesystem_avail_bytes[6h], 4*3600) < 0`) plus inode alerts, cap log verbosity via config not code, and capacity review with owners

## Follow-ups
- You delete a 40 GB log file and `df` shows no change. Explain why and give two ways to reclaim the space.
- The growth is PostgreSQL WAL. Walk me through what you check and what you must not do.
- Write the alerting rule you'd want and justify the threshold and window — why is 90% full a bad alert on a 10 TB volume?
- Logs are on the same partition as the database data files. What's your migration plan, and how do you do it without downtime?

## Sample answer
First, how long do I have and is the service already hurting? `df -h` plus `df -i` — inodes can run out with space free — and the growth rate from the monitoring graph gives me minutes-to-full, plus whether writes are already failing or the filesystem risks going read-only.

Then find the growth: `du -xh --max-depth=1` walking down the tree, `find -xdev -size +1G -mtime -1`, and `lsof +L1` for deleted-but-open files, because if a process holds the fd, `rm` frees nothing — you truncate via `/proc/PID/fd/N` instead. Safe levers: force logrotate, gzip old logs, vacuum the journal, prune old images and core dumps, move data to another volume, and if the platform allows, just grow the volume with `lvextend`/`resize2fs`. I don't `rm -rf` anything I can't explain, and I won't touch database WAL, audit or retained data without the owner — retained WAL usually means an inactive replication slot or a broken archive_command, and deleting it breaks recovery.

I'd also check the rest of the fleet, because the same growth is almost certainly on every peer.

Next week: logrotate with size and age plus compression, real retention, ship logs off-box, separate partitions so logs can't fill the data volume, and alert on projected time-to-full — `predict_linear` over six hours — plus inodes, instead of a static 90%.
