# Troubleshooting Framework (PE / SRE)

## The 7-step framework
1. **Characterise** — what exactly is broken? Scope, blast radius, when it started.
2. **Reproduce / observe** — get a live signal; don't theorise blind.
3. **Hypothesise** — list candidate causes ordered by likelihood.
4. **Eliminate systematically** — test one variable at a time; bisect.
5. **Confirm root cause** — name the *specific* failure, not a category.
6. **Apply simplest safe fix** — reversible first; preserve data.
7. **Prevent fleet-wide** — monitoring/alert/automation so it can't recur silently.

## Golden questions
- "What changed?" (deploys, config, traffic, dependencies)
- "Is it one box or the fleet?"
- "When did it start, and what else happened then?"
- "Is it getting worse, stable, or recovering?"

## Data-preservation phrases (say these out loud in a mock)
- "Before I touch anything, let me capture the current state."
- "Is this safe to run on a production node, or should I test on one box first?"
- "Let me snapshot logs / take a heap dump before restarting."

## Fleet-wide prevention framing
A senior answer never ends at "I restarted it." End with: alert on the leading
indicator, add a runbook, automate the remediation, or fix the class of bug.

## Scoring you're judged on
Discovery questions · systematic elimination · correct tool selection ·
reading output correctly · data preservation · simplest safe fix ·
scalable (fleet-wide) prevention.
