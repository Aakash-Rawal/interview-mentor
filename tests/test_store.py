"""Markdown question store: parse/render round-trip, validation, numbering."""
from datetime import date

import pytest

from question_bank import store

SAMPLE = {
    "id": "ne-routing-041", "domain": "ne", "topic": "routing", "difficulty": "hard",
    "tags": ["bgp", "leak"], "companies": ["meta"], "source": "generated",
    "created": date(2026, 9, 12),
    "prompt": "A prefix-list change made you a transit AS. What happened?",
    "look_for": ["Names it a route leak", "Reverts before diagnosing"],
    "covers": ["Export filter missing", "Default-deny export policy; communities; max-prefix"],
    "follow_ups": ["How would RPKI have helped?"],
    "sample_answer": "This is a route leak: ...",
}


def test_render_parse_roundtrip(tmp_path, monkeypatch):
    text = store.render_question(SAMPLE)
    assert text.startswith("---\nid: ne-routing-041\n") and "created: 2026-09-12\n" in text
    q = store.parse_question(text)
    for k in ("id", "domain", "topic", "difficulty", "tags", "companies", "source", "created",
              "prompt", "look_for", "covers", "follow_ups", "sample_answer"):
        assert q[k] == SAMPLE[k], k
    assert q["expected_answer_notes"] == "Export filter missing. Default-deny export policy; communities; max-prefix."


def test_parse_accepts_hand_written_lists_and_rejects_bad_files():
    q = store.parse_question("""---
id: pe-linux-900
domain: pe
topic: linux
difficulty: easy
---
# Prompt
Why is load 12 on 4 cores not necessarily a CPU problem?
## Strong answer covers
- D-state tasks count
* vmstat b column
3) iowait
""")
    assert q["covers"] == ["D-state tasks count", "vmstat b column", "iowait"]
    assert q["source"] == "manual" and q["created"] == date.today()
    with pytest.raises(ValueError, match="frontmatter"):
        store.parse_question("# Prompt\nno front matter")
    with pytest.raises(ValueError, match="unknown topic"):
        store.parse_question("---\nid: x-y-1\ndomain: pe\ntopic: bgp\n---\n# Prompt\nq\n## Strong answer covers\n- a\n")
    with pytest.raises(ValueError, match="Strong answer covers"):
        store.parse_question("---\nid: pe-linux-1\ndomain: pe\ntopic: linux\n---\n# Prompt\nq\n")


def test_save_load_next_id_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "QUESTIONS_DIR", tmp_path)
    store.invalidate()
    assert store.load_all() == [] and store.next_id("ne", "routing") == "ne-routing-001"
    path = store.save_question(SAMPLE)
    assert path == tmp_path / "ne" / "routing" / "ne-routing-041.md"
    assert store.next_id("ne", "routing") == "ne-routing-042"
    assert store.get("ne-routing-041")["prompt"] == SAMPLE["prompt"]
    (tmp_path / "ne" / "routing" / "broken.md").write_text("garbage")
    store.invalidate()
    assert len(store.load_all()) == 1 and "broken.md" in store.load_errors()[0]
    assert store.delete_question("ne-routing-041") and store.get("ne-routing-041") is None
    assert not store.delete_question("nope")
    store.invalidate()
