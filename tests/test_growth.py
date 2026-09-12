"""Question generator + review queue + skill editor. Claude is mocked; Postgres is real."""
import json

import pytest

import config


def test_generator_cleans_dedups_and_stores(monkeypatch):
    pytest.importorskip("psycopg2")
    from question_bank import generator
    from question_bank.questions import get_questions
    existing = get_questions("pe", "linux")[0]["prompt"]
    payload = [
        {"domain": "pe", "topic": "linux", "difficulty": "hard", "tags": ["io", "Disk"],
         "prompt": "A host shows 100% iowait but iostat shows the disk idle. What is going on?",
         "look_for": ["Checks D-state"], "covers": ["NFS hang or hung block device", "ps -eo state"],
         "follow_ups": ["What if it is NFS?"], "sample_answer": "I would start with...",
         "quality_score": 9},
        {"domain": "pe", "topic": "linux", "difficulty": "silly", "tags": [],
         "prompt": existing, "covers": ["duplicate of a seeded question"], "quality_score": 5},
        {"prompt": "too short", "covers": ["x"]},
        {"prompt": "A long enough prompt but no coverage points at all here."},
        "not a dict",
    ]
    monkeypatch.setattr(generator, "call_claude", lambda *a, **k: "here:\n" + json.dumps(payload))
    stored = []
    monkeypatch.setattr(generator.repo, "insert_candidates", lambda rows: stored.extend(rows) or len(rows))
    monkeypatch.setattr(generator.repo, "existing_prompts", lambda topic=None: [existing])
    result = generator.generate_candidates("pe", "linux", 4)
    assert result == {"requested": 4, "returned": 5, "valid": 2, "unique": 1, "stored": 1}
    row = stored[0]
    assert row["source"] == "generated" and row["approved"] is False
    assert row["tags"] == ["io", "disk"] and row["quality_score"] == 9
    assert row["covers"] == ["NFS hang or hung block device", "ps -eo state"]
    assert row["follow_ups"] == ["What if it is NFS?"] and row["look_for"] == ["Checks D-state"]
    assert row["expected_answer_notes"].startswith("NFS hang")
    with pytest.raises(ValueError):
        generator.generate_candidates("pe", "routing", 3)


@pytest.fixture(scope="module")
def client():
    try:
        from db.models import init_db
        init_db()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"postgres not reachable: {exc}")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
    from db.connection import get_cursor
    from tests.conftest import purge_user
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM scraped_questions WHERE source = 'pytest'")
    purge_user(config.USER_ID)


def test_review_queue_flow(client, tmp_path, monkeypatch):
    from db import repo
    from question_bank import store
    from question_bank.questions import get_questions
    monkeypatch.setattr(store, "QUESTIONS_DIR", tmp_path)   # temp bank, real DB queue
    store.invalidate()
    # count only what this test's domain-filtered pages see
    pending_before = len([c for c in repo.list_candidates("ne") if c["source"] != "pytest"])
    repo.insert_candidates([{
        "source": "pytest", "source_id": "r1", "domain": "ne", "topic": "routing",
        "difficulty": "easy", "tags": ["bgp"], "prompt": "PYTEST candidate: what is a BGP community?",
        "expected_answer_notes": "Tagging routes for policy; well-known vs extended.",
        "quality_score": 8, "approved": False, "raw_text": None}])
    cid = next(c["id"] for c in repo.list_candidates("ne") if c["source"] == "pytest")
    page = client.get("/questions/review?domain=ne").text
    assert "PYTEST candidate" in page and f"{pending_before + 1} pending" in page
    assert "needs coverage points" in page

    r = client.post(f"/api/questions/{cid}/update", data={
        "domain": "ne", "topic": "routing", "difficulty": "medium",
        "prompt": "PYTEST candidate: explain BGP communities and one real use.",
        "look_for": "Knows well-known communities\nGives a policy example",
        "covers": "1. Tagging for policy (no-export)\n2. Extended communities\n\n- local-pref signalling",
        "follow_ups": "- How do you strip inbound communities?", "sample_answer": "Communities are...",
        "tags": "bgp, Communities", "companies": "meta",
        "approve": "1"}, follow_redirects=False)
    assert r.status_code == 303 and "promoted=ne-routing-001" in r.headers["location"]
    q = store.get("ne-routing-001")
    assert q["covers"] == ["Tagging for policy (no-export)", "Extended communities", "local-pref signalling"]
    assert q["tags"] == ["bgp", "communities"] and q["companies"] == ["meta"] and q["source"] == "pytest"
    assert q["follow_ups"] == ["How do you strip inbound communities?"] and q["difficulty"] == "medium"
    assert (tmp_path / "ne" / "routing" / "ne-routing-001.md").exists()
    assert get_questions("ne", "routing", difficulty="medium")[0]["id"] == "ne-routing-001"
    assert "PYTEST candidate" in client.get("/questions?domain=ne").text
    assert repo.get_candidate(cid)["promoted_id"] == "ne-routing-001"

    # edit the bank file through the editor page
    assert "Extended communities" in client.get("/questions/q/ne-routing-001").text
    r = client.post("/api/questions/file/ne-routing-001", data={
        "difficulty": "hard", "prompt": q["prompt"], "covers": "only one point", "tags": "bgp"},
        follow_redirects=False)
    assert r.status_code == 303
    assert store.get("ne-routing-001")["covers"] == ["only one point"]

    # back to the queue: file removed, row pending again
    client.post(f"/api/questions/{cid}/unapprove", data={"domain": "ne"}, follow_redirects=False)
    assert store.get("ne-routing-001") is None and repo.get_candidate(cid)["approved"] is False
    client.post(f"/api/questions/{cid}/reject", data={"domain": "ne"}, follow_redirects=False)
    assert repo.get_candidate(cid) is None
    store.invalidate()


def test_skill_editor_roundtrip(client, tmp_path, monkeypatch):
    from agents.base import load_skill
    monkeypatch.setattr(config, "SKILLS_DIR", tmp_path)
    (tmp_path / "ne").mkdir()
    (tmp_path / "ne" / "routing_protocols.md").write_text("# old\n")
    load_skill.cache_clear()
    assert "old" in client.get("/skills/routing").text
    r = client.post("/api/skills/routing", data={"content": "# new\r\nBGP facts\r\n"}, follow_redirects=False)
    assert r.status_code == 303
    assert (tmp_path / "ne" / "routing_protocols.md").read_text() == "# new\nBGP facts\n"
    assert load_skill("routing").startswith("# new")
    assert client.get("/skills").status_code == 200
    assert client.post("/api/skills/nope", data={"content": "x"}).status_code == 404
    load_skill.cache_clear()
