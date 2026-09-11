---
id: ne-sec-01
domain: ne
topic: network_security
difficulty: medium
tags: [acl, firewall, troubleshooting, change-management]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
An ACL change was meant to block one subnet but broke production traffic. How do you reason about what went wrong, and how do you fix it safely?

## What interviewers look for
- Restores service first (roll back the change) before debugging root cause, and says so explicitly
- Reasons from ACL evaluation semantics — first match wins, implicit deny — rather than guessing
- Remembers return traffic on stateless ACLs and asks which direction/interface the ACL was applied to
- Uses evidence: hit counters, logged denies, packet captures, before/after diffs — not speculation
- Turns the fix into a repeatable safe-change process with rollback pre-typed and verification defined

## Strong answer covers
1. Immediate action: roll back to the known-good ACL (or re-apply the saved config), confirm service restored, then investigate — no debugging a broken production path in place
2. First-match-wins ordering: a new `deny ip 10.20.0.0 0.0.255.255 any` inserted above an existing permit shadows it; check sequence numbers (`show access-list`) and where the new ACE landed
3. Implicit deny at the end: if the ACL was newly created or the terminating `permit ip any any` was omitted, everything not explicitly matched is dropped
4. Stateless ACLs need explicit return traffic: outbound permit plus inbound permit for ephemeral ports (1024-65535) or `established`/TCP-ACK matching; a stateful firewall only helps if it sees both directions (asymmetric routing breaks it)
5. Mask/wildcard errors: Cisco wildcard 0.0.0.255 vs netmask 255.255.255.0 inversion, /16 typed instead of /24 so the deny swallows adjacent subnets, or an object-group/prefix-list typo
6. Wrong direction or wrong interface: `in` vs `out`, applied on the wrong SVI/subinterface, or applied to the transit side so it also hits management/monitoring traffic
7. Verification with data: hit counters per ACE before and after (`show access-list`, `clear counters`), ACL logging of denies, syslog, flow logs, and a synthetic test from the source subnet
8. Prevention: peer diff review, config-as-code with lint/CI, narrow rules (specific src/dst/port) over broad ones, canary on one device first, maintenance window, rollback command typed and staged, timed auto-revert (`reload in 10` / commit-confirmed), plus drift detection

## Follow-ups
- The rollback didn't restore service — long-lived TCP sessions stayed dead. What happened and what do you do?
- How would you write this rule so that it's testable before it touches production — what tooling or dry-run would you build?
- The same subnet must be blocked to one app but allowed to another on the same VLAN. Does an ACL remain the right control, or would you move enforcement elsewhere?
- Your platform is cloud security groups rather than router ACLs. Which of these failure modes disappear and which new ones appear?

## Sample answer
First I restore service: roll back to the previous ACL and confirm with a synthetic test and the app's error rate, then investigate. The failure is almost always one of four things. Ordering — ACLs are first match wins, so a new deny inserted above an existing permit shadows it; I check sequence numbers in `show access-list`. Implicit deny — if the ACL was new, everything not explicitly permitted got dropped, so the missing `permit ip any any` is the bug. Return traffic — an ACL is stateless, so if I permitted outbound to a server but didn't permit the return to ephemeral ports or match `established`, the flow dies one way; a stateful firewall only saves you if it sees both directions. And masks or direction — a wildcard typed as a netmask, a /16 where I meant /24, or the ACL applied `in` instead of `out`, or on the wrong interface. Evidence, not guessing: hit counters per line before and after, ACL deny logging, flow logs. Then I re-apply narrowly — specific source, destination and port — on a canary device in a window, with the rollback command already typed and ideally a commit-confirmed timer. Prevention is diff review, config-as-code with CI validation, and drift detection so the rule set stays what we reviewed.
