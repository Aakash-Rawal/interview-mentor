"""Endpoints the pages call: streaming chat turns, mock lifecycle, settings.

Streaming responses are plain chunked text/plain; the browser reads the body
with fetch() and appends deltas as they arrive. An error mid-stream is sent as
a final line starting with the ERROR_MARKER so the client can show it.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

import config
from agents.base import ClaudeError, load_skill
from agents.interviewer import Interviewer
from agents.planner import Planner, bank_text, performance_text
from agents.tutor import Tutor
from context.learner import build_context
from db import repo

router = APIRouter()
USER = config.USER_ID
ERROR_MARKER = "\n\x1e ERROR: "   # record separator — never appears in normal prose
RESUME_SUFFIXES = (".pdf", ".docx", ".txt")

tutor = Tutor()
interviewer = Interviewer()
planner = Planner()


def _back(path: str, **params) -> RedirectResponse:
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v)
    return RedirectResponse(f"{path}?{query}" if query else path, status_code=303)


def _stream(gen: Iterator[str], on_complete) -> StreamingResponse:
    def body():
        chunks: list[str] = []
        try:
            for piece in gen:
                chunks.append(piece)
                yield piece
        except ClaudeError as exc:
            yield f"{ERROR_MARKER}{exc}"
            return
        except Exception as exc:  # noqa: BLE001 — surface anything to the UI
            yield f"{ERROR_MARKER}{type(exc).__name__}: {exc}"
            return
        on_complete("".join(chunks))
    return StreamingResponse(body(), media_type="text/plain; charset=utf-8",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ----------------------------------------------------------------- resumes
@router.post("/resumes")
async def upload_resume(file: UploadFile | None = File(None), text: str = Form("")):
    """Store the base resume, from a .pdf/.docx/.txt upload or pasted text."""
    from agents.resume_agent import parse_resume_file   # lazy: pulls in pdfminer/docx
    content = text.strip()
    file_name = None
    if file is not None and file.filename:
        file_name = Path(file.filename).name          # never trust the client's path
        if Path(file_name).suffix.lower() not in RESUME_SUFFIXES:
            return _back("/settings", resume_error="Use a .pdf, .docx or .txt file.")
        dest = config.UPLOADS_DIR / file_name
        dest.write_bytes(await file.read())
        try:
            content = parse_resume_file(str(dest)).strip()
        except Exception as exc:  # noqa: BLE001 — pdfminer/docx raise all sorts
            return _back("/settings", resume_error=f"Could not read that file: {exc}")
    if len(content) < 80:
        return _back("/settings", resume_error="That resume looks empty — paste the text or "
                                               "upload a file with selectable text.")
    repo.save_resume(USER, content, file_name=file_name, is_base=True)
    return _back("/settings", saved="1")


# ------------------------------------------------------------------- plans
@router.post("/plans")
def create_plan(jd_text: str = Form(...), company: str = Form(""), role: str = Form(""),
                domain: str = Form("auto"), interview_date: str = Form("")):
    """Analyse the pasted JD against the stored resume and persist the plan.

    Blocking: one high-effort Claude call, same pattern as question generation.
    """
    resume = repo.get_base_resume(USER)
    if not resume:
        return _back("/plans/new", error="Add your resume in Settings first.")
    when = None
    if interview_date.strip():
        try:
            when = date.fromisoformat(interview_date.strip())
        except ValueError:
            return _back("/plans/new", error="Interview date must be YYYY-MM-DD.")
    user = repo.get_user(USER)
    try:
        plan = planner.build_plan(
            resume["content_text"], jd_text,
            domain=domain if domain in config.DOMAINS else None,
            performance=performance_text(USER), bank=bank_text(), model=user.get("model"))
    except ValueError as exc:
        return _back("/plans/new", error=str(exc))
    except ClaudeError as exc:
        return _back("/plans/new", error=str(exc))
    if plan.get("error"):
        return _back("/plans/new", error="Claude's plan could not be parsed. Try again.")
    if not plan["focus_areas"]:
        return _back("/plans/new", error="No focus areas came back — the job description may be "
                                         "too vague, or it may not be a PE/SRE or network role.")
    target_id = repo.create_target(
        USER, jd_text=jd_text.strip(), company=company.strip() or plan["company"],
        role=role.strip() or plan["role"], domain=plan["domain"], seniority=plan["seniority"],
        resume_id=resume["id"], interview_date=when, summary=plan["summary"],
        strengths=plan["strengths"], unmapped=plan["unmapped"])
    repo.add_focus_areas(target_id, plan["focus_areas"])
    repo.update_user(USER, current_domain=plan["domain"])
    return RedirectResponse(f"/plans/{target_id}", status_code=303)


@router.post("/plans/{target_id}/status")
def set_plan_status(target_id: int, status: str = Form(...)):
    if status not in ("active", "archived"):
        raise HTTPException(400, "unknown status")
    repo.set_target_status(target_id, USER, status)
    return RedirectResponse("/plans" if status == "archived" else f"/plans/{target_id}",
                            status_code=303)


@router.post("/plans/{target_id}/delete")
def delete_plan(target_id: int):
    """Drops the plan and its focus areas. Chats and mocks stay, unlinked."""
    repo.delete_target(target_id, USER)
    return RedirectResponse("/plans", status_code=303)


# ------------------------------------------------------------- focus areas
@router.post("/focus/{focus_id}/status")
def set_focus_status(focus_id: int, status: str = Form(...)):
    focus = repo.get_focus(focus_id, USER)
    if not focus:
        raise HTTPException(404)
    if status not in config.FOCUS_STATUSES:
        raise HTTPException(400, "unknown status")
    repo.set_focus_status(focus_id, USER, status)
    return RedirectResponse(f"/plans/{focus['target_id']}#f{focus_id}", status_code=303)


@router.post("/focus/{focus_id}/learn")
def learn_focus(focus_id: int):
    """Start a tutor session on a focus area. The chat carries the job context."""
    focus = repo.get_focus(focus_id, USER)
    if not focus:
        raise HTTPException(404)
    conv_id = repo.create_conversation(USER, focus["domain"], focus["topic"],
                                       focus["title"][:120], focus_id=focus_id)
    if focus["status"] == "todo":
        repo.set_focus_status(focus_id, USER, "studying")
    repo.update_user(USER, current_domain=focus["domain"])
    return RedirectResponse(f"/learn/{conv_id}", status_code=303)


@router.post("/focus/{focus_id}/mock")
def mock_focus(focus_id: int, difficulty: str = Form("any"), hints: str | None = Form(None)):
    """Start a mock on a focus area, preferring questions that match its JD vocabulary."""
    focus = repo.get_focus(focus_id, USER)
    if not focus:
        raise HTTPException(404)
    if repo.get_active_mock(USER):
        raise HTTPException(409, "a mock is already in progress — finish or abandon it first")
    question = interviewer.pick_question(
        focus["domain"], focus["topic"], difficulty, repo.covered_question_ids(USER),
        prefer_tags=focus.get("keywords") or [])
    if not question:
        raise HTTPException(404, "no questions in the bank for this focus area's topic yet")
    mock_id = repo.create_mock(USER, focus["domain"], focus["topic"], question,
                               question["difficulty"], bool(hints), focus_id=focus_id)
    if focus["status"] == "todo":
        repo.set_focus_status(focus_id, USER, "studying")
    repo.update_user(USER, current_domain=focus["domain"])
    return RedirectResponse(f"/mock/{mock_id}", status_code=303)


# ------------------------------------------------------------------ learn
@router.post("/conversations")
def create_conversation(domain: str = Form(...), topic: str = Form(...)):
    if domain not in config.DOMAINS or topic not in config.TOPICS[domain]:
        raise HTTPException(400, "unknown domain/topic")
    conv_id = repo.create_conversation(USER, domain, topic, f"New {config.topic_label(topic)} session")
    repo.update_user(USER, current_domain=domain)
    return RedirectResponse(f"/learn/{conv_id}", status_code=303)


@router.post("/conversations/{conv_id}/messages")
def send_message(conv_id: int, text: str = Form(...)):
    conv = repo.get_conversation(conv_id, USER)
    if not conv:
        raise HTTPException(404)
    text = text.strip()
    if not text:
        raise HTTPException(400, "empty message")
    history = repo.list_messages(conv_id)
    if not history:
        repo.rename_conversation(conv_id, Tutor.title_from(text))
    repo.add_message(conv_id, "user", text)
    focus = repo.get_focus(conv["focus_id"], USER) if conv.get("focus_id") else None
    ctx = build_context(USER, conv["domain"], conv["topic"], exclude_conversation=conv_id,
                        focus=focus)

    def done(reply: str):
        if reply.strip():
            repo.add_message(conv_id, "assistant", reply)

    return _stream(tutor.stream_reply(ctx, history, text), done)


@router.post("/conversations/{conv_id}/archive")
def archive_conversation(conv_id: int):
    repo.archive_conversation(conv_id, USER)
    return RedirectResponse("/learn", status_code=303)


# ------------------------------------------------------------------- mock
@router.post("/mocks")
def start_mock(domain: str = Form(...), topic: str = Form(...),
               difficulty: str = Form("any"), hints: str | None = Form(None)):
    if domain not in config.DOMAINS or topic not in config.TOPICS[domain]:
        raise HTTPException(400, "unknown domain/topic")
    if repo.get_active_mock(USER):
        raise HTTPException(409, "a mock is already in progress")
    question = interviewer.pick_question(domain, topic, difficulty, repo.covered_question_ids(USER))
    if not question:
        raise HTTPException(404, "no questions for that topic")
    mock_id = repo.create_mock(USER, domain, topic, question, question["difficulty"], bool(hints))
    repo.update_user(USER, current_domain=domain)
    return RedirectResponse(f"/mock/{mock_id}", status_code=303)


@router.post("/mocks/{mock_id}/turns")
def mock_turn(mock_id: int, text: str = Form(...)):
    mock = repo.get_mock(mock_id, USER)
    if not mock or mock["status"] != "active":
        raise HTTPException(404, "no active mock")
    text = text.strip()
    if not text:
        raise HTTPException(400, "empty message")
    ctx = build_context(USER, mock["domain"], mock["topic"], focus=_mock_focus(mock))

    def done(reply: str):
        turns = [{"role": "user", "content": text}]
        if reply.strip():
            turns.append({"role": "assistant", "content": reply})
        repo.append_mock_turns(mock_id, turns)

    return _stream(interviewer.stream_turn(ctx, mock, text), done)


@router.post("/mocks/{mock_id}/finish")
def finish_mock(mock_id: int):
    mock = repo.get_mock(mock_id, USER)
    if not mock or mock["status"] != "active":
        raise HTTPException(404, "no active mock")
    if len(mock["transcript"]) < 2:
        return JSONResponse({"error": "Answer at least once before scoring."}, status_code=400)
    ctx = build_context(USER, mock["domain"], mock["topic"], focus=_mock_focus(mock))
    try:
        score = interviewer.score(ctx, mock)
    except ClaudeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    if "error" in score:
        return JSONResponse({"error": score["error"]}, status_code=502)
    repo.finish_mock(mock_id, score)
    return JSONResponse({"ok": True, "total": score["total"]})


def _mock_focus(mock: dict) -> dict | None:
    return repo.get_focus(mock["focus_id"], USER) if mock.get("focus_id") else None


@router.post("/mocks/{mock_id}/abandon")
def abandon_mock(mock_id: int):
    repo.abandon_mock(mock_id, USER)
    return RedirectResponse("/mock", status_code=303)


# --------------------------------------------------------------- settings
@router.post("/settings")
def save_settings(experience: str = Form(""), language: str = Form(""), notes: str = Form(""),
                  target_role_pe: str = Form(""), target_role_ne: str = Form(""),
                  interview_date: str = Form(""), current_domain: str = Form("pe"),
                  model: str = Form("")):
    when = None
    if interview_date.strip():
        try:
            when = date.fromisoformat(interview_date.strip())
        except ValueError:
            raise HTTPException(400, "interview_date must be YYYY-MM-DD")
    if model and model not in config.MODELS:
        raise HTTPException(400, "unknown model")
    repo.update_user(
        USER,
        background={"experience": experience.strip(), "language": language.strip(),
                    "notes": notes.strip()},
        target_roles={"pe": target_role_pe.strip(), "ne": target_role_ne.strip()},
        interview_date=when,
        current_domain=current_domain if current_domain in config.DOMAINS else "pe",
        model=model or None,
    )
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.get("/health")
def health():
    problems = config.validate()
    try:
        repo.get_user(USER)
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        problems.append(f"database: {exc}")
    return {"ok": db_ok and not problems, "db": db_ok, "problems": problems}


# ------------------------------------------------------- question bank growth
@router.post("/questions/generate")
def generate_questions(domain: str = Form(...), topic: str = Form(...), count: int = Form(10)):
    from question_bank.generator import generate_candidates
    user = repo.get_user(USER)
    try:
        result = generate_candidates(domain, topic, count, model=user.get("model"))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except ClaudeError as exc:
        raise HTTPException(502, str(exc))
    return RedirectResponse(f"/questions/review?domain={domain}&generated={result['stored']}",
                            status_code=303)


def _lines(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-*•").strip()
        line = __import__("re").sub(r"^\d+[.)]\s*", "", line)
        if line:
            out.append(line)
    return out


def _csv(text: str) -> list[str]:
    return [t.strip().lower() for t in (text or "").split(",") if t.strip()]


@router.post("/questions/{cid}/approve")
def approve_question(cid: int, domain: str = Form("pe")):
    from question_bank.review import promote
    try:
        qid = promote(cid)
    except KeyError:
        raise HTTPException(404)
    except ValueError as exc:
        raise HTTPException(400, f"cannot approve: {exc}")
    return RedirectResponse(f"/questions/review?domain={domain}&promoted={qid}", status_code=303)


@router.post("/questions/{cid}/unapprove")
def unapprove_question(cid: int, domain: str = Form("pe")):
    from question_bank.review import demote
    c = repo.get_candidate(cid)
    if c and c.get("promoted_id"):
        demote(c["promoted_id"])
    else:
        repo.update_candidate(cid, approved=False)
    return RedirectResponse(f"/questions/review?domain={domain}", status_code=303)


@router.post("/questions/{cid}/reject")
def reject_question(cid: int, domain: str = Form("pe")):
    repo.delete_candidate(cid)
    return RedirectResponse(f"/questions/review?domain={domain}", status_code=303)


@router.post("/questions/{cid}/update")
def update_question(cid: int, domain: str = Form("pe"), topic: str = Form(...),
                    difficulty: str = Form("medium"), prompt: str = Form(...),
                    look_for: str = Form(""), covers: str = Form(""), follow_ups: str = Form(""),
                    sample_answer: str = Form(""), tags: str = Form(""), companies: str = Form(""),
                    approve: str | None = Form(None)):
    if topic not in config.TOPICS.get(domain, []) or difficulty not in config.DIFFICULTIES:
        raise HTTPException(400, "bad topic/difficulty")
    cov = _lines(covers)
    if len(prompt.strip()) < 10 or not cov:
        raise HTTPException(400, "prompt and at least one coverage point are required")
    repo.update_candidate(
        cid, prompt=prompt.strip(), topic=topic, difficulty=difficulty,
        expected_answer_notes=" ".join(cov), look_for=_lines(look_for), covers=cov,
        follow_ups=_lines(follow_ups), sample_answer=sample_answer.strip(),
        tags=_csv(tags), companies=_csv(companies))
    if approve:
        return approve_question(cid, domain)
    return RedirectResponse(f"/questions/review?domain={domain}#c{cid}", status_code=303)


# ------------------------------------------------------------- bank files
@router.post("/questions/file/{qid}")
def save_bank_question(qid: str, difficulty: str = Form("medium"), prompt: str = Form(...),
                       look_for: str = Form(""), covers: str = Form(""), follow_ups: str = Form(""),
                       sample_answer: str = Form(""), tags: str = Form(""),
                       companies: str = Form("")):
    from question_bank import store
    q = store.get(qid)
    if not q:
        raise HTTPException(404)
    if difficulty not in config.DIFFICULTIES:
        raise HTTPException(400, "bad difficulty")
    cov = _lines(covers)
    if len(prompt.strip()) < 10 or not cov:
        raise HTTPException(400, "prompt and at least one coverage point are required")
    store.save_question({**q, "difficulty": difficulty, "prompt": prompt.strip(),
                         "look_for": _lines(look_for), "covers": cov,
                         "follow_ups": _lines(follow_ups), "sample_answer": sample_answer.strip(),
                         "tags": _csv(tags), "companies": _csv(companies)})
    return RedirectResponse(f"/questions/q/{qid}?saved=1", status_code=303)


@router.post("/questions/file/{qid}/delete")
def delete_bank_question(qid: str):
    from question_bank.review import demote
    from question_bank import store
    q = store.get(qid)
    if not q:
        raise HTTPException(404)
    demote(qid)
    return RedirectResponse(f"/questions?domain={q['domain']}", status_code=303)


# ---------------------------------------------------------------- skill files
@router.post("/skills/{topic}")
def save_skill(topic: str, content: str = Form(...)):
    if topic not in config.SKILL_FILES:
        raise HTTPException(404)
    path = config.SKILLS_DIR / config.SKILL_FILES[topic]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.replace("\r\n", "\n").rstrip() + "\n", encoding="utf-8")
    load_skill.cache_clear()
    return RedirectResponse(f"/skills/{topic}?saved=1", status_code=303)
