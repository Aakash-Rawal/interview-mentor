"""HTML pages. All state lives in PostgreSQL; every page is a fresh read."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import config
from agents.base import check_model, load_skill
from agents.interviewer import RUBRICS
from app.templating import templates
from db import repo
from question_bank import store
from question_bank.questions import all_questions, bank_counts

router = APIRouter()
USER = config.USER_ID


def _domain_arg(request: Request, user: dict) -> str:
    d = request.query_params.get("domain") or user.get("current_domain") or "pe"
    return d if d in config.DOMAINS else "pe"


def _base(request: Request, user: dict, **extra) -> dict:
    ctx = {"user": user, "active_mock": repo.get_active_mock(USER),
           "db_ready": getattr(request.app.state, "db_ready", True)}
    ctx.update(extra)
    return ctx


# ------------------------------------------------------------------ dashboard
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = repo.get_user(USER)
    domain = _domain_arg(request, user)
    summary = repo.performance_summary(USER)
    rows = []
    for topic in config.TOPICS[domain]:
        t = summary.get(domain, {}).get(topic)
        trend = None
        if t and t.get("prev_avg") is not None:
            trend = round(t["last"] - t["prev_avg"], 1)
        rows.append({"topic": topic, "stats": t, "trend": trend})
    days = None
    if user.get("interview_date"):
        from datetime import date
        days = (user["interview_date"] - date.today()).days
    return templates.TemplateResponse(request, "dashboard.html", _base(
        request, user, page="dashboard", domain=domain, rows=rows,
        weak=repo.weak_dimensions(summary, domain),
        recent=repo.list_mocks(USER, status="finished", domain=domain, limit=8),
        recent_chats=repo.list_conversations(USER, domain=domain, limit=6),
        days_to_interview=days, counts=repo.activity_counts(USER),
        config_problems=config.validate(),
    ))


# ---------------------------------------------------------------------- learn
@router.get("/learn", response_class=HTMLResponse)
def learn_index(request: Request):
    user = repo.get_user(USER)
    domain = _domain_arg(request, user)
    return templates.TemplateResponse(request, "learn.html", _base(
        request, user, page="learn", domain=domain, conversation=None, messages=[],
        conversations=repo.list_conversations(USER, domain=domain),
        topic=request.query_params.get("topic") or config.TOPICS[domain][0],
    ))


@router.get("/learn/{conv_id}", response_class=HTMLResponse)
def learn_conversation(request: Request, conv_id: int):
    user = repo.get_user(USER)
    conv = repo.get_conversation(conv_id, USER)
    if not conv:
        return RedirectResponse("/learn", status_code=303)
    return templates.TemplateResponse(request, "learn.html", _base(
        request, user, page="learn", domain=conv["domain"], conversation=conv,
        messages=repo.list_messages(conv_id),
        conversations=repo.list_conversations(USER, domain=conv["domain"]),
        topic=conv["topic"],
    ))


# ----------------------------------------------------------------------- mock
@router.get("/mock", response_class=HTMLResponse)
def mock_index(request: Request):
    user = repo.get_user(USER)
    active = repo.get_active_mock(USER)
    if active:
        return RedirectResponse(f"/mock/{active['id']}", status_code=303)
    domain = _domain_arg(request, user)
    return templates.TemplateResponse(request, "mock.html", _base(
        request, user, page="mock", domain=domain, mock=None,
        topic=request.query_params.get("topic") or config.TOPICS[domain][0],
        history=repo.list_mocks(USER, status="finished", limit=10),
        counts=bank_counts(), covered=repo.covered_question_ids(USER),
    ))


@router.get("/mock/{mock_id}", response_class=HTMLResponse)
def mock_detail(request: Request, mock_id: int):
    user = repo.get_user(USER)
    mock = repo.get_mock(mock_id, USER)
    if not mock:
        return RedirectResponse("/mock", status_code=303)
    return templates.TemplateResponse(request, "mock.html", _base(
        request, user, page="mock", domain=mock["domain"], mock=mock, topic=mock["topic"],
        rubric=RUBRICS.get(mock["topic"], []), history=[], counts={}, covered=set(),
    ))


# ------------------------------------------------------------------ questions
@router.get("/questions", response_class=HTMLResponse)
def questions(request: Request):
    user = repo.get_user(USER)
    domain = _domain_arg(request, user)
    qs = [q for q in all_questions() if q["domain"] == domain]
    by_topic: dict[str, list] = {t: [] for t in config.TOPICS[domain]}
    for q in qs:
        by_topic.setdefault(q["topic"], []).append(q)
    return templates.TemplateResponse(request, "questions.html", _base(
        request, user, page="questions", domain=domain, by_topic=by_topic,
        covered=repo.covered_question_ids(USER), pending=repo.pending_counts().get(domain, 0),
        topic=request.query_params.get("topic") or config.TOPICS[domain][0],
        generated=request.query_params.get("generated"),
        new_since=date.today() - timedelta(days=14), bank_errors=store.load_errors(),
        total=len(qs), saved=request.query_params.get("saved"),
    ))


def _display_path(path) -> str:
    try:
        return str(path.relative_to(config.BASE_DIR))
    except ValueError:
        return str(path)


@router.get("/questions/q/{qid}", response_class=HTMLResponse)
def question_edit(request: Request, qid: str):
    user = repo.get_user(USER)
    q = store.get(qid)
    if not q:
        return RedirectResponse("/questions", status_code=303)
    return templates.TemplateResponse(request, "question_edit.html", _base(
        request, user, page="questions", domain=q["domain"], q=q,
        path=_display_path(store.question_path(q)),
        saved=request.query_params.get("saved") == "1",
    ))


@router.get("/questions/review", response_class=HTMLResponse)
def review(request: Request):
    user = repo.get_user(USER)
    domain = _domain_arg(request, user)
    pending = repo.list_candidates(domain=domain, approved=False)
    by_topic: dict[str, list] = {}
    for c in pending:
        by_topic.setdefault(c["topic"], []).append(c)
    return templates.TemplateResponse(request, "review.html", _base(
        request, user, page="questions", domain=domain, by_topic=by_topic,
        total=len(pending), approved_recent=repo.list_candidates(domain=domain, approved=True)[:15],
    ))


# --------------------------------------------------------------------- skills
def _skill_topics() -> list[dict]:
    out = []
    for topic, rel in config.SKILL_FILES.items():
        path = config.SKILLS_DIR / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        out.append({"topic": topic, "label": config.topic_label(topic) if topic in config.TOPIC_LABELS
                    else topic.replace("_", " ").title(), "rel": rel,
                    "domain": config.domain_for_topic(topic) or "shared",
                    "lines": text.count("\n"), "words": len(text.split())})
    return out


@router.get("/skills", response_class=HTMLResponse)
def skills(request: Request):
    user = repo.get_user(USER)
    return templates.TemplateResponse(request, "skills.html", _base(
        request, user, page="skills", domain=user.get("current_domain", "pe"),
        skills=_skill_topics(), saved=request.query_params.get("saved"),
    ))


@router.get("/skills/{topic}", response_class=HTMLResponse)
def skill_edit(request: Request, topic: str):
    user = repo.get_user(USER)
    if topic not in config.SKILL_FILES:
        return RedirectResponse("/skills", status_code=303)
    return templates.TemplateResponse(request, "skill_edit.html", _base(
        request, user, page="skills", domain=user.get("current_domain", "pe"),
        topic=topic, rel=config.SKILL_FILES[topic], content=load_skill(topic),
        saved=request.query_params.get("saved") == "1",
    ))


# ------------------------------------------------------------------- settings
@router.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    user = repo.get_user(USER)
    key_status = None
    if request.query_params.get("check") == "1":
        key_status = check_model(user.get("model") or config.DEFAULT_MODEL)
    return templates.TemplateResponse(request, "settings.html", _base(
        request, user, page="settings", domain=user.get("current_domain", "pe"),
        saved=request.query_params.get("saved") == "1", key_status=key_status,
        key_set=bool(config.ANTHROPIC_API_KEY), env_path=str(config.BASE_DIR / ".env"),
        default_model=config.DEFAULT_MODEL, db_url=config.DATABASE_URL,
    ))
