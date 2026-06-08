"""Offline smoke test — verifies wiring without calling Claude or Postgres."""
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-dummy-for-import-test")

import config
from context.shared_context import SharedContext
from question_bank.questions import get_questions, QUESTIONS
from agents.orchestrator import Orchestrator
from agents.base import load_skill

failures = []

def check(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        failures.append(name)

print("\n1. config sanity")
check("two domains (pe, ne)", set(config.DOMAINS) == {"pe", "ne"})
check("every topic maps to a skill file", all(
    t in config.SKILL_FILES for ts in config.TOPICS.values() for t in ts))
check("every skill file actually exists on disk", all(
    (config.SKILLS_DIR / rel).exists() for rel in config.SKILL_FILES.values()))

print("\n2. SharedContext JSON round-trip (Postgres serialisation)")
from datetime import date
ctx = SharedContext(user_id="t", current_domain="ne", current_topic="routing",
                    interview_date=date(2026, 7, 1))
ctx.add_exchange("user", "hi")
ctx.record_score("ne", "routing", {"total": 7.5, "question_id": "ne-rt-01"})
back = SharedContext.from_json(ctx.to_json())
check("round-trips domain", back.current_domain == "ne")
check("round-trips interview_date as date", back.interview_date == date(2026, 7, 1))
check("round-trips performance_data", back.performance_data["ne"]["routing"][0]["total"] == 7.5)
check("from_json drops unknown keys safely",
      SharedContext.from_json('{"user_id":"x","bogus":1}').user_id == "x")

print("\n3. question bank filtering")
check("NE routing questions exist", len(get_questions("ne", "routing")) >= 1)
check("exclude_ids works", all(
    q["id"] != "ne-rt-01"
    for q in get_questions("ne", "routing", exclude_ids={"ne-rt-01"})))
check("every question has required fields", all(
    {"id", "domain", "topic", "difficulty", "prompt", "expected_answer_notes"} <= set(q)
    for q in QUESTIONS))
check("every question domain is pe or ne", all(q["domain"] in ("pe", "ne") for q in QUESTIONS))

print("\n4. skill loading")
check("routing skill loads and mentions BGP", "BGP" in load_skill("routing"))
check("ats skill loads", "ATS" in load_skill("ats"))

print("\n5. orchestrator routing (no API calls)")
orch = Orchestrator()
c = SharedContext(user_id="t")
orch._maybe_switch_domain(c, "switch to network engineering")
check("domain switch to ne", c.current_domain == "ne")
check("detects bgp -> routing topic", orch._detect_topic(c, "explain bgp") == "routing")
orch._maybe_switch_domain(c, "switch to pe")
check("domain switch back to pe", c.current_domain == "pe")
check("detects coding topic", orch._detect_topic(c, "a coding problem") == "coding")
check("progress summary handles empty data",
      "No mock scores" in orch._progress_summary(SharedContext(user_id="t")))

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURE(S): {failures}"))
raise SystemExit(1 if failures else 0)
