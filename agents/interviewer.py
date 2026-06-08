"""Mock Interviewer agent — conducts mocks turn by turn, then scores.

Pulls a question from the bank (filtering out already-covered ones via
performance_data), runs the mock conversationally, and at the end produces a
structured rubric score that is written to performance_data and persisted to
the scores table.
"""
import json

from agents.base import load_skill, call_claude
from context.shared_context import SharedContext
from question_bank.questions import get_questions, get_question_by_id

# Rubric dimensions per topic. Each scored 0-10 at the end of a mock.
RUBRICS = {
    "coding": [
        "problem_clarification", "data_structure_choice", "code_correctness",
        "edge_case_handling", "time_space_complexity", "memory_safety",
        "talking_through_reasoning",
    ],
    "linux": [
        "discovery_questions", "systematic_elimination", "correct_command_selection",
        "reading_output_correctly", "data_preservation", "fix_quality",
        "scalable_prevention",
    ],
    "troubleshooting": [
        "discovery_questions", "systematic_elimination", "correct_tool_selection",
        "reading_output_correctly", "data_preservation", "fix_quality",
        "scalable_prevention",
    ],
    "system_design": [
        "requirements_gathering", "scale_estimation", "component_design",
        "failure_mode_analysis", "tradeoff_articulation", "observability",
    ],
    # --- Network Engineering rubrics ---
    "network_troubleshooting": [
        "layer_isolation", "tool_selection", "protocol_knowledge",
        "blast_radius_awareness", "root_cause_precision", "fix_and_prevention",
    ],
    "routing": [
        "protocol_knowledge", "path_selection_reasoning", "failure_analysis",
        "blast_radius_awareness", "root_cause_precision", "fix_and_prevention",
    ],
    "networking_fundamentals": [
        "conceptual_accuracy", "layer_isolation", "practical_application",
        "edge_case_handling", "reasoning_clarity",
    ],
    "network_design": [
        "requirements_gathering", "topology_choice", "routing_design",
        "failure_mode_analysis", "capacity_planning", "tradeoff_articulation",
    ],
    "network_security": [
        "threat_modeling", "control_selection", "blast_radius_awareness",
        "root_cause_precision", "fix_and_prevention",
    ],
}

# Default rubric if a topic isn't mapped above.
DEFAULT_RUBRIC = ["correctness", "reasoning_clarity", "depth", "communication"]

CONDUCT_SYSTEM = """You are a rigorous but fair {domain} mock interviewer at a top tech company.

You are conducting a mock on this question:
---
{question}
---
Expected-answer notes (for YOU only, never reveal directly): {notes}

Rules:
- Act like a real interviewer. Let the candidate drive. Ask probing follow-ups.
- Do NOT give away the answer. {hint_rule}
- One step at a time. Wait for their response before moving on.
- If they're stuck, nudge with a question, not the solution.
- Keep your turns short.

Reference material you may quietly draw on:
{skill}"""

SCORE_SYSTEM = """You are scoring a completed {domain} mock interview.
Score each rubric dimension from 0-10 with one short justification grounded in
what the candidate actually said. Be honest — unearned high scores don't help them.

Return ONLY valid JSON in exactly this shape:
{{
  "dimensions": {{ "<dimension>": {{"score": <0-10>, "note": "<short>"}}, ... }},
  "total": <average of scores, one decimal>,
  "summary": "<2-3 sentence overall assessment>",
  "top_fix": "<the single highest-leverage thing to improve>"
}}

Dimensions to score: {dimensions}"""


class Interviewer:
    def __init__(self):
        self.active = False
        self.question: dict | None = None
        self.transcript: list[dict] = []
        self.topic: str | None = None

    # ---- lifecycle ----
    def start_mock(self, ctx: SharedContext, topic: str, hints: bool = False) -> str:
        seen = self._covered_ids(ctx)
        candidates = get_questions(domain=ctx.current_domain, topic=topic, exclude_ids=seen)
        if not candidates:
            # Everything covered — allow repeats rather than dead-end.
            candidates = get_questions(domain=ctx.current_domain, topic=topic)
        if not candidates:
            return f"No questions available for {ctx.current_domain}/{topic} yet."

        self.question = candidates[0]
        self.topic = topic
        self.active = True
        self.hints = hints
        self.transcript = []

        domain_label = {"pe": "Production Engineering / SRE",
                        "ne": "Network Engineering"}.get(ctx.current_domain, ctx.current_domain)
        opener = (f"**Mock started — {domain_label} / {topic}** "
                  f"(say `done` when you want to finish and be scored)\n\n"
                  f"**Interviewer:** {self.question['prompt']}")
        self.transcript.append({"role": "assistant", "content": self.question["prompt"]})
        return opener

    def turn(self, ctx: SharedContext, user_input: str) -> str:
        if not self.active or not self.question:
            return "No mock in progress. Say 'start a mock' first."

        skill = load_skill(self.topic)
        domain_label = {"pe": "Production Engineering / SRE",
                        "ne": "Network Engineering"}.get(ctx.current_domain, ctx.current_domain)
        hint_rule = ("Hints are ON: you may give a gentle directional hint if they're stuck."
                     if getattr(self, "hints", False)
                     else "Hints are OFF: do not hint unless they explicitly ask.")
        system = CONDUCT_SYSTEM.format(
            domain=domain_label, question=self.question["prompt"],
            notes=self.question["expected_answer_notes"], skill=skill or "(none)",
            hint_rule=hint_rule,
        )
        self.transcript.append({"role": "user", "content": user_input})
        reply = call_claude(system, self.transcript[-16:])
        self.transcript.append({"role": "assistant", "content": reply})
        return reply

    def finish_mock(self, ctx: SharedContext) -> dict:
        if not self.active or not self.question:
            return {"error": "No mock in progress."}

        dims = RUBRICS.get(self.topic, DEFAULT_RUBRIC)
        domain_label = {"pe": "Production Engineering / SRE",
                        "ne": "Network Engineering"}.get(ctx.current_domain, ctx.current_domain)
        system = SCORE_SYSTEM.format(domain=domain_label, dimensions=", ".join(dims))
        convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in self.transcript)
        raw = call_claude(
            system,
            [{"role": "user", "content": f"Question:\n{self.question['prompt']}\n\n"
                                          f"Transcript:\n{convo}\n\nScore it now."}],
        )
        score = self._parse_json(raw)
        score["question_id"] = self.question["id"]
        score["topic"] = self.topic
        score["domain"] = ctx.current_domain

        ctx.record_score(ctx.current_domain, self.topic, score)
        self._persist(ctx, score)

        self.active = False
        return score

    # ---- helpers ----
    @staticmethod
    def _covered_ids(ctx: SharedContext) -> set:
        ids = set()
        for topics in ctx.performance_data.values():
            for scores in topics.values():
                for s in scores:
                    if s.get("question_id"):
                        ids.add(s["question_id"])
        return ids

    @staticmethod
    def _parse_json(raw: str) -> dict:
        try:
            start, end = raw.index("{"), raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"error": "Could not parse score", "raw": raw}

    @staticmethod
    def _persist(ctx: SharedContext, score: dict) -> None:
        """Best-effort write to the scores table; never crash the mock on DB error."""
        try:
            from db.connection import get_cursor
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "INSERT INTO scores (user_id, domain, topic, question_id, rubric, total) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (ctx.user_id, score.get("domain"), score.get("topic"),
                     score.get("question_id"), json.dumps(score), score.get("total")),
                )
        except Exception as e:  # pragma: no cover - DB optional in early dev
            print(f"  [warn] could not persist score to DB: {e}")
