---
id: pe-lnx-01
domain: pe
topic: linux
difficulty: medium
tags: [disk, inodes, lsof]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
A service reports 'No space left on device' but `df -h` shows 40% free. Walk me through diagnosing it.

## What interviewers look for
- Splits the hypothesis space immediately (inodes vs deleted-open vs wrong filesystem vs reserved blocks) rather than guessing
- Asks which path the write was to and confirms which filesystem that path is actually on
- Preserves data: truncates or rotates rather than rm-ing logs, and captures evidence before restarting the holder
- Reads command output correctly — knows IUse% in df -i and the (deleted) marker in lsof
- Ends on prevention: logrotate with copytruncate, alerting on both blocks and inodes, quota/monitoring across the fleet

## Strong answer covers
1. Runs `df -i` on the target filesystem and interprets IFree/IUse% — millions of tiny files (session dirs, cache, mail spools, unrotated .gz fragments) exhaust inodes while blocks stay free; ext4 inode count is fixed at mkfs time so the fix is delete/move files or recreate the fs
2. Finds deleted-but-open files with `lsof +L1` or `lsof -nP | grep deleted`, explaining that unlink only removes the directory entry; the blocks are freed when the last fd closes, so a log deleted by hand while the daemon holds it still consumes space
3. Frees the space without a restart via `: > /proc/<pid>/fd/<n>` (truncate through the fd) and notes this is safe for append-mode logs but destructive for a database file
4. Confirms the right filesystem/mount: `df -h <path>`, `stat -f <path>`, checks for a write into a directory shadowed by a mount, a full /var separate from /, tmpfs, or a full overlay/container layer
5. Considers 5% root-reserved blocks (`tune2fs -l | grep -i reserved`) so a non-root process sees ENOSPC at ~95%, and read-only remount after errors (`dmesg -T`, `mount | grep ' ro,'`)
6. Uses `du -xh --max-depth=1 / | sort -h` with -x to stay on one filesystem, or `find /path -xdev -type f | wc -l` per directory to locate the inode hog
7. Fix and prevention: proper logrotate (or copytruncate for daemons that don't reopen on SIGHUP), restart/HUP the holder, alert on inode usage as well as bytes, and push the same check to the rest of the fleet

## Follow-ups
- The filesystem is XFS, not ext4 — how does that change the inode story and what would you check?
- You truncate the file and df still shows no change. What else could be holding space?
- The host is a container node and only one container hits ENOSPC. Where do you look?
- How would you write a monitoring check that catches this class of problem before the page?

## Sample answer
First I'd confirm which filesystem the failing write targets — `df -h /path` and `stat -f`, because /var or an overlay layer can be full while / looks fine. Then two classic causes. One: inodes. `df -i` — if IUse% is 100 with blocks free, something has created millions of tiny files; I'd hunt with `du -xh --max-depth=1` and `find -xdev | wc -l`. On ext4 the inode count is fixed at mkfs, so I clean up rather than resize. Two: deleted-but-open files. `lsof +L1` or `lsof -nP | grep deleted` — someone rm'd a log the daemon still has open, so the directory entry is gone but the blocks aren't. I'd free it non-destructively with `: > /proc/<pid>/fd/<n>` rather than restarting and losing state, or HUP the daemon if it reopens logs. I'd also check root-reserved blocks — a non-root writer gets ENOSPC at ~95% — and `dmesg -T` for a filesystem that's gone read-only. Prevention: fix logrotate, use copytruncate for daemons that don't reopen, and add inode-usage alerting alongside bytes, fleet-wide. I wouldn't `rm` logs to buy time; I'd truncate so we keep the fd and the evidence.
