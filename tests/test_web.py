"""Web tests against the real local Postgres (skipped if it is not reachable).

Uses the pytest-user learner id (see conftest) and removes its rows afterwards.
Claude is never called: the streaming agents are monkeypatched.
"""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402


@pytest.fixture(scope="module")
def client():
    try:
        from db.models import init_db
        init_db()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"postgres not reachable: {exc}")
    from app.main import app
    with TestClient(app) as c:
        yield c
    from db.connection import get_cursor
    with get_cursor(commit=True) as cur:
        for table in ("conversation_messages", ):
            cur.execute(f"DELETE FROM {table} WHERE conversation_id IN "
                        f"(SELECT id FROM conversations WHERE user_id = %s)", (config.USER_ID,))
        for table in ("conversations", "mocks", "applications"):
            cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (config.USER_ID,))
        cur.execute("DELETE FROM users WHERE id = %s", (config.USER_ID,))


def test_pages_render(client):
    for path in ("/", "/learn", "/mock", "/questions", "/settings", "/?domain=ne"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "Interview Mentor" in r.text
    assert client.get("/nope").status_code == 404
    assert client.get("/api/health").json()["db"] is True


def test_settings_roundtrip(client):
    r = client.post("/api/settings", data={
        "experience": "5 yrs", "language": "go", "target_role_pe": "Meta PE E5",
        "interview_date": "2026-12-01", "current_domain": "ne", "model": "claude-sonnet-5"},
        follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/settings").text
    assert "5 yrs" in page and "Meta PE E5" in page and "2026-12-01" in page
    assert 'value="claude-sonnet-5" selected' in page


def test_tutor_conversation_flow(client, monkeypatch):
    from app.routes import api

    def fake_reply(ctx, history, text):
        assert ctx.model == "claude-sonnet-5"      # saved in the previous test
        yield "Hello "
        yield f"({len(history)} prior)"
    monkeypatch.setattr(api.tutor, "stream_reply", fake_reply)

    r = client.post("/api/conversations", data={"domain": "ne", "topic": "routing"},
                    follow_redirects=False)
    conv_url = r.headers["location"]                       # /learn/<id>
    api_url = f"/api/conversations/{conv_url.rsplit('/', 1)[1]}"
    r = client.post(f"{api_url}/messages", data={"text": "What is BGP local pref?"})
    assert r.status_code == 200 and r.text == "Hello (0 prior)"
    r = client.post(f"{api_url}/messages", data={"text": "and MED?"})
    assert r.text == "Hello (2 prior)"
    page = client.get(conv_url).text
    assert "What is BGP local pref?" in page and "Hello (2 prior)" in page


def test_tutor_stream_error_is_reported(client, monkeypatch):
    from agents.base import ClaudeError
    from app.routes import api

    def boom(ctx, history, text):
        yield "partial"
        raise ClaudeError("key rejected")
    monkeypatch.setattr(api.tutor, "stream_reply", boom)
    r = client.post("/api/conversations", data={"domain": "pe", "topic": "linux"},
                    follow_redirects=False)
    conv_id = r.headers["location"].rsplit("/", 1)[1]
    r = client.post(f"/api/conversations/{conv_id}/messages", data={"text": "hi"})
    assert r.text.startswith("partial") and api.ERROR_MARKER in r.text and "key rejected" in r.text


def test_mock_lifecycle(client, monkeypatch):
    from app.routes import api

    monkeypatch.setattr(api.interviewer, "stream_turn",
                        lambda ctx, mock, text: iter(["Why ", "that?"]))
    monkeypatch.setattr(api.interviewer, "score", lambda ctx, mock: {
        "dimensions": {"protocol_knowledge": {"score": 8, "note": "ok"},
                       "failure_analysis": {"score": 4, "note": "thin"}},
        "total": 6.0, "summary": "Decent.", "top_fix": "Cover failure modes.",
        "model_answer": "- hold timer\n- withdraw"})

    r = client.post("/api/mocks", data={"domain": "ne", "topic": "routing", "difficulty": "hard",
                                        "hints": "1"}, follow_redirects=False)
    mock_url = r.headers["location"]                       # /mock/<id>
    api_url = f"/api/mocks/{mock_url.rsplit('/', 1)[1]}"
    # second start is refused while one is active; /mock redirects to it
    assert client.post("/api/mocks", data={"domain": "ne", "topic": "routing"}).status_code == 409
    assert client.get("/mock", follow_redirects=False).headers["location"] == mock_url

    assert client.post(f"{api_url}/finish").status_code == 400   # nothing answered yet
    r = client.post(f"{api_url}/turns", data={"text": "Hold timer expires…"})
    assert r.text == "Why that?"
    assert client.post(f"{api_url}/finish").json()["total"] == 6.0

    page = client.get(mock_url).text
    assert "Cover failure modes." in page and "Failure analysis" in page and "finished" in page
    dash = client.get("/?domain=ne").text
    assert "Failure analysis" in dash and "6.0" in dash
    # the question is now excluded from future picks
    from db import repo
    assert repo.covered_question_ids(config.USER_ID)
