"""Live end-to-end verification. REQUIRES a real ANTHROPIC_API_KEY (.env) and a
running PostgreSQL with the interview_prep database. Makes a handful of real
(billable) Claude calls. Run from the project root:

    ./.venv/bin/python tests/live_check.py
"""
import sys

import config
from db.connection import get_cursor
from db.models import init_db, ensure_user
from context.shared_context import SharedContext
from agents.orchestrator import Orchestrator
from agents.base import get_client, load_skill

USER = "live-check-user"
fails = []

def ok(name, cond, extra=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' — ' + extra) if extra else ''}")
    if not cond:
        fails.append(name)

print("\n1. DB init + schema")
init_db()
with get_cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'")
    tables = {r["table_name"] for r in cur.fetchall()}
for t in ["users", "sessions", "messages", "scores", "resumes", "applications"]:
    ok(f"table '{t}' exists", t in tables)

# Real sessions create the user row at startup; mirror that here.
ensure_user(USER)

orch = Orchestrator()

print("\n2. Tutor (NE / routing) — real Claude call")
ctx = SharedContext(user_id=USER, current_domain="ne", current_topic="routing")
reply = orch.route(ctx, "In two sentences, what is BGP local preference?")
ok("tutor returned non-empty reply", bool(reply.strip()), reply.strip()[:80])

print("\n3. Prompt caching actually engages (large system prefix)")
# Concatenate several skills so the cached prefix clears the model's minimum.
big_system = "\n\n".join(load_skill(t) for t in
                         ["routing", "network_troubleshooting", "network_design",
                          "system_design", "coding"])
def probe():
    r = get_client().messages.create(
        model=config.MODEL_NAME, max_tokens=8,
        system=[{"type": "text", "text": big_system,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "ok"}])
    u = r.usage
    return getattr(u, "cache_creation_input_tokens", 0), getattr(u, "cache_read_input_tokens", 0)
c1, _ = probe()
_, r2 = probe()
ok("cache write then read observed", (c1 > 0 or r2 > 0),
   f"write={c1} read={r2} tokens")

print("\n4. Mock interview: question -> answer -> scored rubric (real calls)")
print("  " + orch.route(ctx, "start a mock").splitlines()[0])
answer = ("The hold timer expires after missed keepalives, the session tears down, "
          "the router withdraws all prefixes learned from that peer, traffic "
          "reconverges onto alternate paths via ECMP, and downstream peers see the "
          "withdrawal. I'd check blast radius and route dampening before acting.")
turn = orch.route(ctx, answer)
ok("interviewer responded to answer", bool(turn.strip()))
score_text = orch.route(ctx, "done")
ok("scoring rendered a total", "Total:" in score_text, score_text.splitlines()[0].strip())
with get_cursor() as cur:
    cur.execute("SELECT count(*) AS n FROM scores WHERE user_id=%s", (USER,))
    n_scores = cur.fetchone()["n"]
ok("score row persisted to Postgres", n_scores >= 1, f"{n_scores} row(s)")

print("\n5. Resume / ATS analysis (real call) + persistence")
resume = ("Aakash Rawal — Production/Network Engineer. Built monitoring for a 200-node "
          "fleet, cut MTTR 30%. Python, Linux, on-call. Configured OSPF in lab.")
jd = ("Seeking a Network Engineer with strong BGP, datacenter spine-leaf design, "
      "Python automation, and Kubernetes experience. On-call required.")
report = orch.run_resume(ctx, "analyze", resume, jd)
ok("ATS analysis returned a score", isinstance(report.get("ats_score"), (int, float)),
   f"ats_score={report.get('ats_score')}")
ok("identified missing keywords", isinstance(report.get("keywords_missing"), list))
with get_cursor() as cur:
    cur.execute("SELECT count(*) AS n FROM applications WHERE user_id=%s", (USER,))
    ok("application row persisted", cur.fetchone()["n"] >= 1)

print("\n6. Session persistence round-trip")
# Save then reload the most recent session for this user.
ctx.interview_date = __import__("datetime").date(2026, 7, 15)
with get_cursor(commit=True) as cur:
    cur.execute("INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (USER,))
    cur.execute("INSERT INTO sessions (user_id, context) VALUES (%s, %s)",
                (USER, ctx.to_json()))
with get_cursor() as cur:
    cur.execute("SELECT context FROM sessions WHERE user_id=%s "
                "ORDER BY updated_at DESC LIMIT 1", (USER,))
    reloaded = SharedContext.from_json(cur.fetchone()["context"])
ok("domain round-trips", reloaded.current_domain == "ne")
ok("interview_date round-trips", str(reloaded.interview_date) == "2026-07-15")
ok("performance_data round-trips", bool(reloaded.performance_data))

# Cleanup this run's rows so reruns stay clean.
with get_cursor(commit=True) as cur:
    cur.execute("DELETE FROM scores WHERE user_id=%s", (USER,))
    cur.execute("DELETE FROM applications WHERE user_id=%s", (USER,))
    cur.execute("DELETE FROM sessions WHERE user_id=%s", (USER,))
    cur.execute("DELETE FROM users WHERE id=%s", (USER,))

print("\n" + ("ALL LIVE CHECKS PASSED" if not fails else f"{len(fails)} FAILURE(S): {fails}"))
sys.exit(1 if fails else 0)
