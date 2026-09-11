---
id: pe-tr-04
domain: pe
topic: troubleshooting
difficulty: hard
tags: [database, connections, cascading]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
The database is reporting 'too many connections' and the whole site is down. Twenty app servers each run a connection pool. Diagnose and fix without making it worse.

## What interviewers look for
- Finds a way to get a connection at all (reserved superuser slots / unix socket) before anything else
- Does the arithmetic: pools × instances versus max_connections, and links it to a recent scale-out
- Distinguishes 'too many idle' from 'connections held by a slow query or open transaction'
- Chooses reversible mitigations and states the blast radius of each (killing sessions, restarting the DB)
- Fixes the structure — pooler, pool sizing from the DB limit, timeouts, alerting — not just the symptom

## Strong answer covers
1. Get access despite the error: PostgreSQL reserves `superuser_reserved_connections` (and `reserved_connections`) slots, or connect over the unix socket from the DB host; in MySQL the `SUPER`/`CONNECTION_ADMIN` extra connection — say this, because candidates often claim they'd run a query they cannot reach
2. Characterise who holds connections: `SELECT state, wait_event_type, application_name, client_addr, count(*) FROM pg_stat_activity GROUP BY 1,2,3,4 ORDER BY 5 DESC;` (or `SHOW FULL PROCESSLIST` / `information_schema.processlist`), and look specifically at `idle in transaction`, long `xact_start`, and `active` sessions with long `query_start`
3. Do the arithmetic: 20 app servers × pool max (e.g. 30) = 600 against `max_connections` = 200; ask what changed — a scale-out from 10 to 20/30 instances, a pool-size config bump, a new cron/analytics client, or a canary fleet running alongside the old one so pools double during deploys
4. Distinguish cause from symptom: if sessions are `active` on slow queries or blocked on locks, connections are a downstream effect — check `pg_locks`/`pg_blocking_pids()`, a long-running migration or `ANALYZE`, a missing index after a deploy, or a replica failover; fixing the slow query releases the connections
5. Mitigate reversibly, cheapest first: shed load at the LB or scale the app tier down, lower the pool max and do a rolling restart of app instances, and terminate only safe sessions — `pg_terminate_backend` filtered on `state='idle in transaction' AND state_change < now() - interval '5 min'` — never blanket-kill `active` sessions; note that a DB restart means crash recovery, cold cache and a thundering-herd reconnect, so it's a last resort
6. Beware the retry/thundering-herd loop: apps that fail to connect immediately retry, so the pressure returns in seconds unless you shed load or cap pools first; the fix must land before or with the kill
7. Durable fix: a connection pooler (PgBouncer/pgcat in transaction mode, or ProxySQL) so DB connections are decoupled from app instance count; size total pool ≤ max_connections − reserve (e.g. 20 hosts × 8 = 160 against 200), set `idle_in_transaction_session_timeout`, `statement_timeout`, sensible `tcp_keepalives`, and pool acquire timeouts so app threads fail fast instead of hanging
8. Detection and process: alert on connection utilisation (e.g. >70% of max) and on pool wait time/saturation, expose pool metrics per service, add a 'connections = instances × pool' check to the scale-out and autoscaling runbook, and cap max app instances accordingly; verify recovery by watching connection count, error rate and p99 back to baseline

## Follow-ups
- You kill the idle-in-transaction sessions and connections are back at the limit in 30 seconds. What's happening and what do you do?
- Someone proposes just raising max_connections from 200 to 1000. Argue both sides, including what happens to memory and throughput.
- What application patterns break under PgBouncer transaction pooling, and how would you find them before rolling it out?
- How would you size the pool from first principles for a service doing 2,000 queries/second with a 5 ms mean query time?

## Sample answer
First, can I even connect? I'd use the superuser-reserved slots or the unix socket on the DB host — otherwise I have no diagnostics. Then I group `pg_stat_activity` by state, client_addr and application_name to see who holds what, and look hard at `idle in transaction` and long-running `active` queries.

The arithmetic usually tells the story: twenty app servers times a pool max of thirty is six hundred against a max_connections of two hundred, and something changed — a scale-out, a pool bump, or a canary fleet doubling pools during a deploy. But I also check whether connections are a symptom: if sessions are active on a slow query or blocked in `pg_locks`, the real fix is killing that query or migration.

Mitigation, most reversible first: shed load at the LB or scale the app tier down, lower pool max and roll app instances, and terminate only sessions that are idle-in-transaction for more than a few minutes — never blanket-kill active work. I'd avoid restarting the DB: crash recovery, cold cache, and every app reconnecting at once.

Durably: put PgBouncer in transaction mode so DB connections stop scaling with instance count, size total pool below max_connections minus reserve, set statement_timeout and idle_in_transaction_session_timeout, add a connection-utilisation alert at 70%, and add the pool×instances check to the scale-out runbook.
