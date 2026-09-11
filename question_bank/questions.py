"""Question bank API. The bank is the markdown files under question_bank/questions/
(see question_bank/README.md and store.py). This module is the query layer.

Each question dict has:
    id, domain, topic, difficulty, tags, companies, source, created,
    prompt, look_for, covers, follow_ups, sample_answer,
    expected_answer_notes (flat prose derived from `covers`, for older call sites)
"""
from __future__ import annotations

from question_bank import store


def all_questions() -> list[dict]:
    return store.load_all()


def get_questions(domain: str | None = None, topic: str | None = None,
                  exclude_ids: set | None = None, difficulty: str | None = None) -> list[dict]:
    exclude_ids = exclude_ids or set()
    return [q for q in all_questions()
            if (not domain or q["domain"] == domain)
            and (not topic or q["topic"] == topic)
            and (not difficulty or q["difficulty"] == difficulty)
            and q["id"] not in exclude_ids]


def get_question_by_id(qid: str) -> dict | None:
    return store.get(qid)


def bank_counts() -> dict:
    """{domain: {topic: count}} across the whole bank."""
    counts: dict = {}
    for q in all_questions():
        counts.setdefault(q["domain"], {}).setdefault(q["topic"], 0)
        counts[q["domain"]][q["topic"]] += 1
    return counts
