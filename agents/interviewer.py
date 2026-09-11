"""Mock Interviewer agent — conducts a mock turn by turn, then scores it.

Stateless: the mock's question and transcript live in the `mocks` table
(db.repo). This module only builds prompts, streams turns, and produces the
rubric score. That makes a mock resumable after a refresh, crash, or restart.
"""
from __future__ import annotations

import json
import random

import config
from agents.base import call_claude, load_skill, stream_claude
from context.learner import LearnerContext
from question_bank.questions import get_questions

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
DEFAULT_RUBRIC = ["correctness", "reasoning_clarity", "depth", "communication"]

TRANSCRIPT_WINDOW = 40

CONDUCT_SYSTEM = """You are a rigorous but fair {domain} interviewer at a top tech company,
running a {difficulty} mock on the topic "{topic}".

Candidate profile: {profile}

The question you asked:
---
{question}
---
For YOU only — never reveal these directly:
What interviewers look for: {look_for}
A strong answer covers:
{covers}
Follow-ups to use when the candidate is doing well (or to test depth), in your own words:
{follow_ups}

Rules:
- Behave like a real interviewer. Let the candidate drive; ask probing follow-ups that
  test depth ("why that?", "what if X fails?", "what does that cost?").
- Never give away the answer. {hint_rule}
- One step at a time: ask one thing, then stop and wait. Keep your turns short (2-6 lines).
- If the candidate is vague, ask for specifics: exact commands, numbers, concrete designs.
- If they say they are done or ask to be scored, tell them to click "Finish & score".
- Plain text or light Markdown. No score, no verdict, no summary during the mock.

Reference material you may quietly draw on:
{skill}
"""

SCORE_SYSTEM = """You are scoring a completed {domain} mock interview ({difficulty}) on "{topic}".
Score each rubric dimension from 0-10, with one short justification grounded in what
the candidate actually said. Be honest and calibrated: 5 is a borderline hire, 8+ is
a clear strong hire signal, and unearned high scores do not help the candidate.
If a dimension was never exercised, score it low and say so in the note.

Return ONLY valid JSON in exactly this shape, no prose around it:
{{
  "dimensions": {{ "<dimension>": {{"score": <0-10>, "note": "<short>"}}, ... }},
  "coverage": [ {{"point": "<coverage point, copied>", "covered": true|false, "note": "<where/why>"}}, ... ],
  "total": <average of the dimension scores, one decimal>,
  "summary": "<2-3 sentence overall assessment>",
  "top_fix": "<the single highest-leverage thing to improve>",
  "model_answer": "<compact outline of what a strong answer would have covered, 4-8 bullet lines>"
}}

Dimensions to score: {dimensions}

Coverage points to check, one entry each, in order:
{covers}"""


class Interviewer:
    # ---- question selection ---------------------------------------------
    @staticmethod
    def pick_question(domain: str, topic: str, difficulty: str | None,
                      exclude_ids: set[str], rng: random.Random | None = None) -> dict | None:
        rng = rng or random.Random()
        pool = get_questions(domain=domain, topic=topic, exclude_ids=exclude_ids)
        if difficulty and difficulty != "any":
            wanted = [q for q in pool if q["difficulty"] == difficulty]
            pool = wanted or pool
        if not pool:  # everything covered — allow repeats rather than dead-end
            pool = get_questions(domain=domain, topic=topic)
            if difficulty and difficulty != "any":
                pool = [q for q in pool if q["difficulty"] == difficulty] or pool
        return rng.choice(pool) if pool else None

    # ---- prompts --------------------------------------------------------
    def conduct_prompt(self, ctx: LearnerContext, mock: dict) -> str:
        q = mock["question"]
        hint_rule = ("Hints are ON: if they are stuck, give one gentle directional hint."
                     if mock.get("hints") else
                     "Hints are OFF: do not hint unless they explicitly ask for one.")
        return CONDUCT_SYSTEM.format(
            domain=ctx.domain_label, topic=ctx.topic_label, difficulty=mock["difficulty"],
            profile=ctx.profile_text(), question=q["prompt"],
            look_for=_join(q.get("look_for")) or "(not specified)",
            covers=_numbered(q.get("covers")) or q.get("expected_answer_notes", ""),
            follow_ups=_bulleted(q.get("follow_ups")) or "(improvise)",
            hint_rule=hint_rule, skill=load_skill(mock["topic"]) or "(none)",
        )

    @staticmethod
    def api_messages(transcript: list[dict], user_input: str | None = None) -> list[dict]:
        """Transcript -> Messages API list. The stored transcript starts with the
        interviewer's question (assistant), so a synthetic user opener goes first."""
        msgs = [{"role": "user", "content": "I'm ready. Please ask the question."}]
        msgs += [{"role": m["role"], "content": m["content"]}
                 for m in transcript[-TRANSCRIPT_WINDOW:]]
        if user_input is not None:
            msgs.append({"role": "user", "content": user_input})
        return msgs

    # ---- turns ----------------------------------------------------------
    def stream_turn(self, ctx: LearnerContext, mock: dict, user_input: str):
        yield from stream_claude(
            self.conduct_prompt(ctx, mock),
            self.api_messages(mock["transcript"], user_input),
            max_tokens=config.MAX_TOKENS_CHAT, effort=config.EFFORT_CHAT, model=ctx.model)

    # ---- scoring --------------------------------------------------------
    def score(self, ctx: LearnerContext, mock: dict) -> dict:
        dims = RUBRICS.get(mock["topic"], DEFAULT_RUBRIC)
        q = mock["question"]
        system = SCORE_SYSTEM.format(
            domain=ctx.domain_label, topic=ctx.topic_label, difficulty=mock["difficulty"],
            dimensions=", ".join(dims),
            covers=_numbered(q.get("covers")) or q.get("expected_answer_notes", ""))
        convo = "\n\n".join(
            f"{'INTERVIEWER' if m['role'] == 'assistant' else 'CANDIDATE'}: {m['content']}"
            for m in mock["transcript"])
        raw = call_claude(
            system,
            [{"role": "user", "content":
              f"Question:\n{q['prompt']}\n\n"
              f"What interviewers look for: {_join(q.get('look_for')) or '(n/a)'}\n\n"
              f"Transcript:\n{convo}\n\nScore it now."}],
            max_tokens=config.MAX_TOKENS_LONG, effort=config.EFFORT_SCORE, model=ctx.model)
        score = parse_json_object(raw)
        score.setdefault("dimensions", {})
        score["total"] = _coerce_total(score, dims)
        cov = [c for c in (score.get("coverage") or []) if isinstance(c, dict)]
        score["coverage"] = cov
        if cov:
            score["coverage_hit"] = sum(1 for c in cov if c.get("covered"))
            score["coverage_total"] = len(cov)
        return score


def parse_json_object(raw: str) -> dict:
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"error": "Could not parse score", "raw": raw}


def _coerce_total(score: dict, dims: list[str]) -> float | None:
    vals = []
    for d in dims:
        detail = score["dimensions"].get(d) or {}
        try:
            vals.append(float(detail.get("score")))
        except (TypeError, ValueError):
            pass
    if vals:
        return round(sum(vals) / len(vals), 1)
    try:
        return round(float(score.get("total")), 1)
    except (TypeError, ValueError):
        return None


def _join(items) -> str:
    return "; ".join(str(i).strip() for i in (items or []) if str(i).strip())


def _numbered(items) -> str:
    return "\n".join(f"{n}. {str(i).strip()}" for n, i in enumerate(items or [], 1) if str(i).strip())


def _bulleted(items) -> str:
    return "\n".join(f"- {str(i).strip()}" for i in (items or []) if str(i).strip())
