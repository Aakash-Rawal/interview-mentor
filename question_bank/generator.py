"""Generate and enrich questions with Claude.

generate_candidates(): new questions for a topic → review queue (unapproved).
enrich(): fill the structured sections (look-for, coverage, follow-ups, sample
answer) for questions that only have a prompt and prose notes.

Both prompts carry the authoring rules from question_bank/README.md and the
topic's skill file, so output matches what the tutor teaches.
"""
from __future__ import annotations

import json
import uuid

import config
from agents.base import call_claude, load_skill
from db import repo
from question_bank.extractor import _parse_json_array, deduplicate

AUTHORING_RULES = """Authoring rules (non-negotiable):
- Self-contained prompt: everything needed to answer is in it. No answer leakage.
- Realistic production framing: incidents, designs under constraints, "what do you check
  first", reading output, trade-off comparisons. Not trivia.
- No company names inside the prompt text. Put them in "companies" if the question is known
  to be asked somewhere.
- Difficulty = time to a strong answer: easy 3-5 min, medium 8-12 min, hard 15-20 min with
  several dimensions most candidates miss.
- "look_for": 3-5 signals a strong candidate shows (behaviours, not facts).
- "covers": 4-8 numbered, checkable coverage points with specifics — commands, numbers,
  protocol behaviour, trade-offs. Scoring reports which of these the candidate hit.
- "follow_ups": 2-4 escalating probes an interviewer asks when the candidate is doing well,
  each testing something the coverage list does not already cover.
- "sample_answer": 120-250 words of spoken prose, the way a strong candidate would say it."""

FIELDS = """  "prompt": string,
  "look_for": [string, ...],
  "covers": [string, ...],
  "follow_ups": [string, ...],
  "sample_answer": string,
  "tags": [1-4 short lowercase keywords],
  "companies": [] ,
  "difficulty": "easy" | "medium" | "hard",
  "quality_score": integer 0-10 (your honest rating of usefulness)"""

GEN_SYSTEM = """You write mock-interview questions for {domain} interviews at top-tier tech
companies. Topic: "{topic}". You have run hundreds of these loops.

## Reference material for this topic (what our tutor treats as ground truth)
{skill}

## Editorial guidance
{focus}

{rules}

## Questions we already have for this topic — do NOT duplicate or lightly rephrase them
{existing}

## Output
Return ONLY a JSON array of exactly {n} objects (mix roughly 30% easy / 40% medium / 30% hard),
each with these keys:
{{
{fields}
}}
Vary the angles across the batch."""

ENRICH_SYSTEM = """You are completing a question bank for {domain} interviews, topic "{topic}".
Each question below has a prompt and short prose notes. For EACH, write the structured
sections. Keep the prompt unchanged. Preserve every specific in the notes and add more.

## Reference material for this topic
{skill}

{rules}

## Output
Return ONLY a JSON array with one object per input question, in the same order, keyed by id:
{{
  "id": string (copy exactly),
  "look_for": [string, ...],
  "covers": [string, ...],
  "follow_ups": [string, ...],
  "sample_answer": string,
  "tags": [1-4 short lowercase keywords]
}}"""


def generate_candidates(domain: str, topic: str, n: int = 10,
                        model: str | None = None) -> dict:
    if domain not in config.DOMAINS or topic not in config.TOPICS[domain]:
        raise ValueError("unknown domain/topic")
    n = max(1, min(int(n), 15))
    existing = repo.existing_prompts(topic=topic)
    system = GEN_SYSTEM.format(
        domain=config.DOMAINS[domain], topic=config.topic_label(topic),
        skill=load_skill(topic) or "(none)", focus=load_skill("scraper_focus") or "(none)",
        rules=AUTHORING_RULES, existing="\n".join(f"- {p}" for p in existing) or "(none yet)",
        n=n, fields=FIELDS)
    raw = call_claude(system, [{"role": "user", "content": f"Write {n} questions now."}],
                      max_tokens=config.MAX_TOKENS_BATCH, effort=config.EFFORT_SCORE, model=model)
    parsed = _parse_json_array(raw)
    candidates = [c for c in (_clean(item, domain, topic) for item in parsed) if c]
    unique = deduplicate(candidates, existing)
    stored = repo.insert_candidates(unique)
    return {"requested": n, "returned": len(parsed), "valid": len(candidates),
            "unique": len(unique), "stored": stored}


def enrich(questions: list[dict], model: str | None = None) -> dict[str, dict]:
    """questions: dicts with id, domain, topic, prompt, expected_answer_notes (same topic).
    Returns {id: {look_for, covers, follow_ups, sample_answer, tags}}."""
    if not questions:
        return {}
    domain, topic = questions[0]["domain"], questions[0]["topic"]
    system = ENRICH_SYSTEM.format(domain=config.DOMAINS[domain], topic=config.topic_label(topic),
                                  skill=load_skill(topic) or "(none)", rules=AUTHORING_RULES)
    payload = [{"id": q["id"], "prompt": q["prompt"], "notes": q.get("expected_answer_notes", "")}
               for q in questions]
    raw = call_claude(system, [{"role": "user", "content": json.dumps(payload, indent=1)}],
                      max_tokens=config.MAX_TOKENS_BATCH, effort=config.EFFORT_SCORE, model=model)
    out = {}
    for item in _parse_json_array(raw):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        fields = _structured(item)
        if fields["covers"]:
            out[str(item["id"])] = fields
    return out


# ------------------------------------------------------------------ helpers
def _strlist(v, limit: int = 12) -> list[str]:
    from question_bank.store import clean_item
    if isinstance(v, str):
        v = [v]
    return [clean_item(x) for x in (v or []) if clean_item(x)][:limit]


def _structured(item: dict) -> dict:
    return {
        "look_for": _strlist(item.get("look_for")),
        "covers": _strlist(item.get("covers")),
        "follow_ups": _strlist(item.get("follow_ups")),
        "sample_answer": str(item.get("sample_answer") or "").strip(),
        "tags": [t.lower()[:30] for t in _strlist(item.get("tags"), 4)],
    }


def _clean(item: dict, domain: str, topic: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    prompt = str(item.get("prompt", "")).strip()
    fields = _structured(item)
    if len(prompt) < 20 or not fields["covers"]:
        return None
    difficulty = str(item.get("difficulty", "medium")).lower()
    if difficulty not in config.DIFFICULTIES:
        difficulty = "medium"
    try:
        quality = max(0, min(10, int(item.get("quality_score", 7))))
    except (TypeError, ValueError):
        quality = 7
    return {"source": "generated", "source_id": uuid.uuid4().hex, "domain": domain,
            "topic": topic, "difficulty": difficulty, "prompt": prompt,
            "expected_answer_notes": " ".join(fields["covers"]),
            "companies": _strlist(item.get("companies"), 6),
            "quality_score": quality, "approved": False, "raw_text": None, **fields}
