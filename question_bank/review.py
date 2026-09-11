"""Review queue → bank files. Approving a candidate writes its markdown file."""
from __future__ import annotations

from datetime import date

from db import repo
from question_bank import store


def candidate_to_question(c: dict, qid: str) -> dict:
    covers = list(c.get("covers") or [])
    if not covers and (c.get("expected_answer_notes") or "").strip():
        covers = [c["expected_answer_notes"].strip()]
    return {
        "id": qid, "domain": c["domain"], "topic": c["topic"],
        "difficulty": c.get("difficulty") or "medium",
        "tags": list(c.get("tags") or []), "companies": list(c.get("companies") or []),
        "source": c.get("source") or "generated", "created": date.today(),
        "prompt": c["prompt"], "look_for": list(c.get("look_for") or []), "covers": covers,
        "follow_ups": list(c.get("follow_ups") or []),
        "sample_answer": c.get("sample_answer") or "",
    }


def promote(cid: int) -> str:
    """Write the candidate as a bank file and mark the row approved. Returns the new id."""
    c = repo.get_candidate(cid)
    if not c:
        raise KeyError(cid)
    if c.get("promoted_id") and store.get(c["promoted_id"]):
        return c["promoted_id"]
    qid = store.next_id(c["domain"], c["topic"])
    store.save_question(candidate_to_question(c, qid))
    repo.mark_promoted(cid, qid)
    return qid


def demote(qid: str) -> bool:
    """Remove a bank file; if it came from the queue, put the row back in the queue."""
    removed = store.delete_question(qid)
    repo.unmark_promoted(qid)
    return removed
