---
id: pe-cod-09
domain: pe
topic: coding
difficulty: medium
tags: [graph, bfs, dependencies]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
Services declare dependencies on other services. Given the dependency list, produce a safe startup order, and detect if there is a cycle.

## What interviewers look for
- Names topological sort immediately and picks Kahn or DFS deliberately
- Detects cycles as a first-class outcome and reports which nodes are involved, not just 'cycle exists'
- States O(V+E) and what V and E are in the operational domain
- Raises real-world wrinkles: missing nodes, self-dependencies, multiple valid orders, parallel start groups
- Connects it to actual tooling — systemd units, deploy DAGs, Terraform graphs

## Strong answer covers
1. Builds an adjacency list plus in-degree map from the dependency pairs, being explicit about edge direction (dependency -> dependent) so the output order is actually safe to start in
2. Kahn's algorithm: seed a queue with all in-degree-0 nodes, pop and emit, decrement successors' in-degrees, push those that hit zero — O(V+E) time and space
3. Cycle detection: if the emitted count is less than the node count, the remaining nodes with nonzero in-degree form one or more cycles; reports them so an operator can act. DFS alternative uses three colours (white/grey/black) and finds a cycle when it re-enters a grey node, which gives the actual cycle path
4. Handles graph hygiene: services that appear only as dependencies must still become nodes, duplicate edges, self-dependencies (an immediate 1-cycle), and dependencies on services that don't exist in the inventory
5. Notes that topological order is not unique; if determinism matters for reproducible deploys, use a heap instead of a FIFO to break ties by name and produce a stable order
6. Produces parallel start 'waves': everything at in-degree 0 in the same round can start concurrently, which is how you actually parallelise a startup or deploy, and reports the critical path length as the minimum number of waves
7. Connects to real systems: systemd After/Requires ordering, container orchestrator init dependencies, deploy pipelines, Terraform's resource graph — all the same algorithm, and all of them report dependency cycles as a hard error
8. Mentions the operational caveat that 'dependency declared' is not 'dependency ready' — ordering still needs readiness checks/health gating, and mutual dependencies in reality are broken with retry loops or degraded startup rather than a strict order

## Follow-ups
- You find a cycle between three services. As the engineer on call during a cold start, what do you actually do?
- Give me the maximum parallelism version: which groups start together, and what's the critical path?
- The dependency list is generated from service discovery and is occasionally wrong. How do you make startup robust to a bad graph?
- How would you extend this to weighted startup times to estimate total cold-start duration?

## Sample answer
This is a topological sort. I build an adjacency list from dependency to dependent plus an in-degree count per service, making sure services that appear only as someone's dependency still get created as nodes. Then Kahn's algorithm: queue everything with in-degree zero, pop and emit, decrement each successor, enqueue any that reach zero. O(V+E) in services and dependency edges. Cycle detection falls out for free — if I've emitted fewer nodes than exist, whatever remains with nonzero in-degree is in or downstream of a cycle, and I report those names rather than just 'cycle detected', because an operator needs to know which three services are deadlocked. If I need the exact cycle path, DFS with grey/black colouring gives it. A few things I'd raise: the order isn't unique, so if we want reproducible deploys I'd break ties deterministically with a heap on service name; self-dependencies and duplicate edges need handling; and the more useful output is usually waves — all in-degree-zero nodes per round start in parallel, and the number of rounds is the critical path. This is exactly what systemd does with After and Requires, and what Terraform does with its resource graph. Practically, ordering isn't enough — you still gate on readiness, and real mutual dependencies get broken with retry loops rather than a perfect order.
