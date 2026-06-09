"""LLM-powered extraction and deduplication for scraped raw posts.

Flow for a single RawPost:
  1. Call Claude to extract structured interview questions from the raw text.
  2. For each extracted question, check it is not a near-duplicate of anything
     already in the hardcoded bank or the scraped_questions table.
  3. Return ExtractedQuestion dicts ready for the pipeline to persist.

Dedup strategy (no vector DB required for Phase 2):
  - Normalise the prompt text (lowercase, strip punctuation, collapse whitespace).
  - Compute a simple n-gram overlap score against known prompts.
  - Reject if overlap > DEDUP_THRESHOLD (default 0.7).

This keeps the dependency footprint light — ChromaDB is the Phase 2 upgrade path.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import TypedDict

from agents.base import call_claude, load_skill
from question_bank.scraper import RawPost
import config


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ExtractedQuestion(TypedDict):
    source: str
    source_id: str
    domain: str
    topic: str
    difficulty: str
    tags: list[str]
    prompt: str
    expected_answer_notes: str
    quality_score: int       # 0-10 from Claude
    approved: bool           # True if quality_score >= threshold
    raw_text: str


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = """\
You are a technical interview question analyst for Production Engineering (PE/SRE)
and Network Engineering (NE) roles.

Your job: read a raw forum post and extract every genuine technical interview
question you find, whether stated explicitly ("They asked me…") or implied by
the discussion.

Valid domains:  pe  |  ne
Valid topics:
  pe  → coding | linux | troubleshooting | system_design
  ne  → networking_fundamentals | routing | network_troubleshooting |
         network_design | network_security

For EACH question you find, produce one JSON object with these exact keys:
  domain            (string)
  topic             (string)
  difficulty        ("easy" | "medium" | "hard")
  tags              (list of 1-4 short keyword strings)
  prompt            (the interview question, clean and self-contained, 1-4 sentences)
  expected_answer_notes  (what a strong answer covers, 1-3 sentences)
  quality_score     (integer 0-10: how useful is this as a mock interview question?
                     10 = precise, tests real skill; 1 = vague / off-topic)

Return ONLY a JSON array, e.g.:
[
  {"domain": "pe", "topic": "linux", "difficulty": "medium",
   "tags": ["disk", "inodes"],
   "prompt": "...", "expected_answer_notes": "...", "quality_score": 8},
  ...
]

If the post contains no relevant interview questions, return an empty array: []
Do NOT include commentary outside the JSON.
"""


def _build_system_prompt() -> str:
    """Combine the fixed extraction rules with the editable focus file.

    The focus file (skills/scraper/extraction_focus.md) is loaded via the same
    load_skill() path used by every other agent — cached after first read.
    """
    focus = load_skill("scraper_focus")
    if focus:
        return _EXTRACTION_SYSTEM + "\n\n---\n\n" + focus
    return _EXTRACTION_SYSTEM


def extract_questions(post: RawPost) -> list[ExtractedQuestion]:
    """Call Claude to extract structured questions from one RawPost.

    Returns an empty list on any error so the pipeline can continue.
    """
    truncated_text = post["raw_text"][:6000]  # guard against huge posts
    messages = [{"role": "user", "content": truncated_text}]

    try:
        raw = call_claude(
            system=_build_system_prompt(),
            messages=messages,
            max_tokens=2000,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[extractor] Claude call failed for {post['source_id']}: {exc}")
        return []

    items = _parse_json_array(raw)
    if not isinstance(items, list):
        return []

    results: list[ExtractedQuestion] = []
    valid_domains = set(config.DOMAINS)
    valid_topics = {t for ts in config.TOPICS.values() for t in ts}

    for item in items:
        if not isinstance(item, dict):
            continue
        domain = item.get("domain", "")
        topic = item.get("topic", "")
        prompt = item.get("prompt", "").strip()

        # Structural validation.
        if domain not in valid_domains or topic not in valid_topics or not prompt:
            continue
        # Topic must belong to the stated domain.
        if topic not in config.TOPICS.get(domain, []):
            continue

        quality = int(item.get("quality_score", 0))
        results.append(ExtractedQuestion(
            source=post["source"],
            source_id=post["source_id"],
            domain=domain,
            topic=topic,
            difficulty=item.get("difficulty", "medium"),
            tags=item.get("tags", []) if isinstance(item.get("tags"), list) else [],
            prompt=prompt,
            expected_answer_notes=item.get("expected_answer_notes", "").strip(),
            quality_score=quality,
            approved=quality >= config.SCRAPER_AUTO_APPROVE_THRESHOLD,
            raw_text=post["raw_text"],
        ))

    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _ngrams(text: str, n: int = 3) -> set[str]:
    """Return the set of character n-grams for a normalised string."""
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def _overlap(a: str, b: str, n: int = 3) -> float:
    """Jaccard overlap of character n-gram sets. Returns 0.0–1.0."""
    na, nb = _ngrams(_normalise(a), n), _ngrams(_normalise(b), n)
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)


DEDUP_THRESHOLD = 0.70


def is_duplicate(prompt: str, existing_prompts: list[str]) -> bool:
    """Return True if prompt is too similar to any string in existing_prompts."""
    for ep in existing_prompts:
        if _overlap(prompt, ep) >= DEDUP_THRESHOLD:
            return True
    return False


def deduplicate(
    candidates: list[ExtractedQuestion],
    existing_prompts: list[str],
) -> list[ExtractedQuestion]:
    """Filter candidates, removing near-duplicates of existing prompts or each other.

    Args:
        candidates:       Questions extracted from raw posts.
        existing_prompts: All prompts already in the bank (hardcoded + DB).

    Returns:
        Unique candidates only. Also deduplicates within the batch itself.
    """
    seen = list(existing_prompts)
    unique: list[ExtractedQuestion] = []
    for q in candidates:
        if not is_duplicate(q["prompt"], seen):
            unique.append(q)
            seen.append(q["prompt"])
    return unique


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_array(raw: str) -> list:
    """Extract the first JSON array from a Claude response string."""
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
