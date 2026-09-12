"""Job plans: planner validation, focus-aware prompts, and the plan → study wiring.

Claude is never called: Planner.build_plan is monkeypatched. Postgres is real
(the web tests skip if it is not reachable).
"""
import pytest

import config

# A plan as the planner would return it, before normalisation.
RAW_PLAN = {
    "company": "Cloudflare", "role": "Staff Production Engineer", "domain": "pe",
    "seniority": "staff",
    "summary": "The loop is weighted to container operations and incident response.",
    "focus_areas": [
        {"title": "Kubernetes resource limits and pod evictions", "topic": "linux",
         "level": "tool", "priority": 2,
         "why_jd": "Operate workloads on Kubernetes at scale",
         "gap": "Resume shows VMs and bare metal, no container orchestration",
         "keywords": ["kubernetes", "OOMKilled", "memory", "memory"]},
        {"title": "Debugging a saturated host under load", "topic": "troubleshooting",
         "level": "concept", "priority": 1,
         "why_jd": "Own production incidents end to end", "gap": "One on-call line, no depth",
         "keywords": ["incident", "latency"]},
        {"title": "Terraform module design", "topic": "infrastructure_as_code",
         "priority": 3, "why_jd": "Manage infra as code", "gap": "No IaC on the resume"},
    ],
    "strengths": ["8 years of Linux performance work, with numbers"],
    "unmapped": ["Windows Active Directory administration"],
}


def _plan():
    from agents.planner import normalise_plan
    return normalise_plan(RAW_PLAN)


# ------------------------------------------------------------------ validation
def test_normalise_plan_closes_the_topic_set_and_resequences():
    plan = _plan()
    topics = [a["topic"] for a in plan["focus_areas"]]
    assert topics == ["troubleshooting", "linux"]          # reordered by priority
    assert [a["priority"] for a in plan["focus_areas"]] == [1, 2]
    assert all(t in config.TOPICS[plan["domain"]] for t in topics)

    # A focus area with no real topic is surfaced, not silently dropped.
    assert any("Terraform module design" in u for u in plan["unmapped"])
    assert "Windows Active Directory administration" in plan["unmapped"]

    tool = next(a for a in plan["focus_areas"] if a["topic"] == "linux")
    assert tool["level"] == "tool"
    assert tool["keywords"] == ["kubernetes", "oomkilled", "memory"]   # lowered, deduped
    # A tool focus area keeps the JD's framing instead of being rewritten as theory.
    assert tool["title"].startswith("Kubernetes")
    concept = next(a for a in plan["focus_areas"] if a["topic"] == "troubleshooting")
    assert concept["level"] == "concept"


def test_normalise_plan_defaults_and_caps():
    from agents.planner import normalise_plan
    raw = {"focus_areas": [
        {"title": f"Area {i}", "topic": "linux", "priority": i} for i in range(12)]}
    plan = normalise_plan(raw, "pe")
    assert len(plan["focus_areas"]) == config.MAX_FOCUS_AREAS
    assert len(plan["unmapped"]) == 12 - config.MAX_FOCUS_AREAS
    assert plan["focus_areas"][0]["level"] == "concept"   # unspecified level
    assert plan["focus_areas"][0]["keywords"] == []
    # No usable domain in the output: infer it from the topics.
    assert normalise_plan({"focus_areas": [{"title": "Routing", "topic": "routing"}]})["domain"] == "ne"
    assert normalise_plan({"error": "nope"}) == {"error": "nope"}


def test_planner_prompt_closes_topics_and_keeps_tools_at_usage_level():
    from agents.planner import Planner
    prompt = Planner().system_prompt("pe", "no mocks", "- linux: 8")
    assert "closed list" in prompt
    # Every topic is offered even though the domain is pinned: a PE job that leans on
    # routing should get a routing focus area rather than lose the requirement.
    for topic in list(config.TOPICS["pe"]) + list(config.TOPICS["ne"]):
        assert topic in prompt
    assert "Tools are not concepts" in prompt
    assert '"level": "tool"' in prompt


def test_focus_area_from_the_other_domain_is_kept():
    from agents.planner import normalise_plan
    plan = normalise_plan({"domain": "pe", "focus_areas": [
        {"title": "Container limits", "topic": "linux"},
        {"title": "BGP path selection at the edge", "topic": "routing"}]}, "pe")
    assert plan["domain"] == "pe"                      # the plan's primary label
    assert [a["topic"] for a in plan["focus_areas"]] == ["linux", "routing"]
    assert plan["unmapped"] == []


# ------------------------------------------------------------- prompt fragments
def _ctx(level: str):
    from context.learner import LearnerContext
    return LearnerContext(
        user_id="u", domain="pe", topic="linux", model="m",
        focus={"title": "Kubernetes resource limits", "level": level, "topic": "linux",
               "why_jd": "Operate Kubernetes at scale", "gap": "No containers on the resume",
               "keywords": ["kubernetes", "oomkilled"], "role": "Staff PE",
               "company": "Cloudflare"})


def test_focus_text_pitches_tools_at_usage_level():
    tool = _ctx("tool").focus_text()
    assert "Staff PE at Cloudflare" in tool
    assert "Kubernetes resource limits" in tool
    assert "kubernetes, oomkilled" in tool
    assert "use and operate it well" in tool
    concept = _ctx("concept").focus_text()
    assert "real depth" in concept and "operate it well" not in concept

    from context.learner import LearnerContext
    assert LearnerContext(user_id="u", domain="pe", topic="linux", model="m").focus_text() == ""


def test_tutor_and_interviewer_prompts_carry_the_focus():
    from agents.interviewer import Interviewer
    from agents.tutor import Tutor
    ctx = _ctx("tool")
    tutor_prompt = Tutor().system_prompt(ctx)
    assert "job-specific prep plan" in tutor_prompt and "Operate Kubernetes at scale" in tutor_prompt

    mock = {"question": {"prompt": "A pod is being killed.", "look_for": [], "covers": ["x"],
                         "follow_ups": []}, "difficulty": "medium", "topic": "linux",
            "hints": False}
    assert "job-specific prep plan" in Interviewer().conduct_prompt(ctx, mock)

    # No focus: the prompts are unchanged general-study prompts.
    from context.learner import LearnerContext
    plain = LearnerContext(user_id="u", domain="pe", topic="linux", model="m")
    assert "job-specific prep plan" not in Tutor().system_prompt(plain)


def test_prefer_tags_narrows_the_question_pool():
    from agents.interviewer import Interviewer, rank_by_tags
    pool = [
        {"id": "a", "prompt": "A pod is OOMKilled repeatedly.", "tags": ["kubernetes"],
         "covers": ["memory limits"]},
        {"id": "b", "prompt": "Disk fills up on a host.", "tags": ["disk"], "covers": ["inodes"]},
        {"id": "c", "prompt": "Memory pressure on a node.", "tags": [], "covers": ["oom"]},
    ]
    assert [q["id"] for q in rank_by_tags(pool, ["kubernetes", "memory"])] == ["a"]
    assert [q["id"] for q in rank_by_tags(pool, ["memory"])] == ["a", "c"]
    assert rank_by_tags(pool, ["bgp"]) == []
    assert rank_by_tags(pool, []) == []

    # A real pick still returns something when nothing matches the JD vocabulary.
    picked = Interviewer.pick_question("pe", "linux", "any", set(), prefer_tags=["bgp"])
    assert picked and picked["topic"] == "linux"


# --------------------------------------------------------------------- web flow
@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    try:
        from db.models import init_db
        init_db()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"postgres not reachable: {exc}")
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c
    from tests.conftest import purge_user
    purge_user(config.USER_ID)


def test_plan_requires_a_resume(client):
    r = client.post("/api/plans", data={"jd_text": "x" * 200}, follow_redirects=False)
    assert r.status_code == 303
    assert "error=Add" in r.headers["location"]
    assert "Add your resume first" in client.get("/plans/new").text


def test_resume_upload_roundtrip(client):
    r = client.post("/api/resumes", data={"text": "too short"}, follow_redirects=False)
    assert "resume_error=" in r.headers["location"]
    r = client.post("/api/resumes", files={"file": ("cv.rtf", b"x" * 200)},
                    follow_redirects=False)
    assert "resume_error=" in r.headers["location"]

    resume = "Senior SRE. 8 years Linux performance work. " + "Ran large fleets. " * 10
    r = client.post("/api/resumes", data={"text": resume}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/settings").text
    assert "8 years Linux performance work" in page


def test_plan_creation_and_study_wiring(client, monkeypatch):
    from app.routes import api
    from db import repo

    seen = {}

    def fake_plan(resume_text, jd_text, **kwargs):
        seen.update(resume=resume_text, jd=jd_text, **kwargs)
        return _plan()

    monkeypatch.setattr(api.planner, "build_plan", fake_plan)
    jd = ("Staff Production Engineer. You will operate workloads on Kubernetes at scale and "
          "own production incidents end to end. " * 3)
    r = client.post("/api/plans", data={"jd_text": jd, "interview_date": "2026-12-01"},
                    follow_redirects=False)
    assert r.status_code == 303
    target_id = int(r.headers["location"].rsplit("/", 1)[1])
    assert "8 years Linux performance work" in seen["resume"]   # the stored resume was used
    assert seen["domain"] is None                               # "auto" means let Claude decide
    assert "linux: " in seen["bank"]

    page = client.get(f"/plans/{target_id}").text
    assert "Kubernetes resource limits and pod evictions" in page
    assert "Debugging a saturated host under load" in page
    assert "Windows Active Directory administration" in page    # unmapped stays visible
    assert "Terraform module design" in page
    assert "8 years of Linux performance work" in page          # strengths
    assert "Staff Production Engineer" in page
    assert "kubernetes" in page                                 # keyword pills

    areas = repo.list_focus_areas(target_id)
    k8s = next(a for a in areas if a["topic"] == "linux")
    assert k8s["status"] == "todo"

    # ---- Learn from a focus area
    r = client.post(f"/api/focus/{k8s['id']}/learn", follow_redirects=False)
    conv_id = int(r.headers["location"].rsplit("/", 1)[1])
    conv_page = client.get(f"/learn/{conv_id}").text
    assert "Kubernetes resource limits and pod evictions" in conv_page
    assert f"/plans/{target_id}" in conv_page
    assert repo.list_focus_areas(target_id)[1]["status"] == "studying"

    captured = {}

    def fake_reply(ctx, history, text):
        captured["focus"] = ctx.focus
        captured["role"] = ctx.target_role
        yield "Start with requests and limits."

    monkeypatch.setattr(api.tutor, "stream_reply", fake_reply)
    assert client.post(f"/api/conversations/{conv_id}/messages",
                       data={"text": "where do I start?"}).status_code == 200
    assert captured["focus"]["level"] == "tool"
    # The seniority is already in the role title, so it is not prepended twice.
    assert captured["role"] == "Staff Production Engineer at Cloudflare"

    # ---- Mock from a focus area
    r = client.post(f"/api/focus/{k8s['id']}/mock", data={"difficulty": "any"},
                    follow_redirects=False)
    assert r.status_code == 303
    mock_id = int(r.headers["location"].rsplit("/", 1)[1])
    mock = repo.get_mock(mock_id, config.USER_ID)
    assert mock["focus_id"] == k8s["id"] and mock["topic"] == "linux"
    mock_page = client.get(f"/mock/{mock_id}").text
    assert "Kubernetes resource limits and pod evictions" in mock_page

    def fake_turn(ctx, m, text):
        captured["mock_focus"] = ctx.focus
        yield "Why that first?"

    monkeypatch.setattr(api.interviewer, "stream_turn", fake_turn)
    assert client.post(f"/api/mocks/{mock_id}/turns",
                       data={"text": "I would check memory limits."}).status_code == 200
    assert captured["mock_focus"]["title"].startswith("Kubernetes")

    # A second mock is refused while one is active, same as the Mock page.
    assert client.post(f"/api/focus/{k8s['id']}/mock").status_code == 409
    client.post(f"/api/mocks/{mock_id}/abandon", follow_redirects=False)

    # ---- Progress is the learner's own call, and it shows on the plan
    client.post(f"/api/focus/{k8s['id']}/status", data={"status": "ready"},
                follow_redirects=False)
    assert client.post(f"/api/focus/{k8s['id']}/status",
                       data={"status": "nonsense"}).status_code == 400
    assert repo.get_focus(k8s["id"], config.USER_ID)["status"] == "ready"
    assert "1 / 2" in client.get(f"/plans/{target_id}").text
    assert "1 of 2 focus areas ready" in client.get("/plans").text

    # ---- Archive, then delete: the plan goes, the study survives
    client.post(f"/api/plans/{target_id}/status", data={"status": "archived"},
                follow_redirects=False)
    plans = client.get("/plans").text
    assert "Archived" in plans and "Reactivate" in plans
    client.post(f"/api/plans/{target_id}/delete", follow_redirects=False)
    assert repo.get_target(target_id, config.USER_ID) is None
    assert repo.get_conversation(conv_id, config.USER_ID) is not None
    assert repo.get_mock(mock_id, config.USER_ID)["focus_id"] is None


def test_plan_errors_are_shown_not_raised(client, monkeypatch):
    from agents.base import ClaudeError
    from app.routes import api

    jd = "Staff Production Engineer operating Kubernetes at scale. " * 5
    for failure, expected in (
            (ClaudeError("Rate limited by Anthropic."), "Rate%20limited"),
            (ValueError("The job description is too short to analyse."), "too%20short"),
    ):
        monkeypatch.setattr(api.planner, "build_plan",
                            lambda *a, **k: (_ for _ in ()).throw(failure))
        r = client.post("/api/plans", data={"jd_text": jd}, follow_redirects=False)
        assert r.status_code == 303 and expected in r.headers["location"]

    monkeypatch.setattr(api.planner, "build_plan", lambda *a, **k: {"error": "unparseable"})
    r = client.post("/api/plans", data={"jd_text": jd}, follow_redirects=False)
    assert "could%20not%20be%20parsed" in r.headers["location"]

    monkeypatch.setattr(api.planner, "build_plan",
                        lambda *a, **k: {**_plan(), "focus_areas": []})
    r = client.post("/api/plans", data={"jd_text": jd}, follow_redirects=False)
    assert "No%20focus%20areas" in r.headers["location"]

    r = client.post("/api/plans", data={"jd_text": jd, "interview_date": "next tuesday"},
                    follow_redirects=False)
    assert "YYYY-MM-DD" in r.headers["location"]
