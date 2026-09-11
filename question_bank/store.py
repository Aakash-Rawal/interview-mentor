"""Question files: one markdown file per question, YAML frontmatter + fixed sections.

    question_bank/questions/<domain>/<topic>/<id>.md

    ---
    id: ne-routing-003
    domain: ne
    topic: routing
    difficulty: hard
    tags: [bgp, convergence]
    companies: []
    source: seed | generated | scraped | manual
    created: 2026-09-11
    ---
    # Prompt
    <the question as the interviewer says it>

    ## What interviewers look for
    - ...

    ## Strong answer covers
    1. ...

    ## Follow-ups
    - ...

    ## Sample answer
    <spoken-prose model answer, optional>

The files are the source of truth for the bank (git-diffable, editable in the
app). The database only holds the review queue and your mock history.
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import yaml

import config

QUESTIONS_DIR = config.BASE_DIR / "question_bank" / "questions"

SECTIONS = {
    "what interviewers look for": "look_for",
    "strong answer covers": "covers",
    "follow-ups": "follow_ups",
    "follow ups": "follow_ups",
    "sample answer": "sample_answer",
}
LIST_FIELDS = ("look_for", "covers", "follow_ups")
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,60}$")


# ------------------------------------------------------------------ parsing
def parse_question(text: str, path: Path | None = None) -> dict:
    m = _FRONT.match(text)
    if not m:
        raise ValueError(f"{path or 'question'}: missing frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    q = {
        "id": str(meta.get("id", "")).strip(),
        "domain": str(meta.get("domain", "")).strip(),
        "topic": str(meta.get("topic", "")).strip(),
        "difficulty": str(meta.get("difficulty", "medium")).strip().lower(),
        "tags": [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()],
        "companies": [str(c).strip() for c in (meta.get("companies") or []) if str(c).strip()],
        "source": str(meta.get("source", "manual")).strip(),
        "created": _as_date(meta.get("created")),
        "prompt": "", "look_for": [], "covers": [], "follow_ups": [], "sample_answer": "",
    }
    # Split the body on headings. "# Prompt" then "## <section>".
    current, buf = None, []
    def flush():
        if current is None:
            return
        chunk = "\n".join(buf).strip()
        if current == "prompt":
            q["prompt"] = chunk
        elif current in LIST_FIELDS:
            q[current] = _as_list(chunk)
        elif current == "sample_answer":
            q["sample_answer"] = chunk
    for line in body.splitlines():
        h = re.match(r"^(#{1,2})\s+(.*?)\s*$", line)
        if h:
            flush()
            title = h.group(2).strip().lower()
            current = "prompt" if title == "prompt" else SECTIONS.get(title)
            buf = []
            continue
        buf.append(line)
    flush()
    q["expected_answer_notes"] = notes_from(q)
    _validate(q, path)
    return q


def render_question(q: dict) -> str:
    meta = {
        "id": q["id"], "domain": q["domain"], "topic": q["topic"],
        "difficulty": q.get("difficulty", "medium"),
        "tags": list(q.get("tags") or []), "companies": list(q.get("companies") or []),
        "source": q.get("source", "manual"),
        "created": _as_date(q.get("created")),
    }
    front = yaml.safe_dump(meta, sort_keys=False, default_flow_style=None,
                           allow_unicode=True, width=1000).strip()
    parts = [f"---\n{front}\n---", f"# Prompt\n{q['prompt'].strip()}"]
    parts.append("## What interviewers look for\n" + _bullets(q.get("look_for")))
    parts.append("## Strong answer covers\n" + _numbered(q.get("covers")))
    parts.append("## Follow-ups\n" + _bullets(q.get("follow_ups")))
    parts.append("## Sample answer\n" + (q.get("sample_answer") or "").strip())
    return "\n\n".join(parts).rstrip() + "\n"


def notes_from(q: dict) -> str:
    """Flat prose used where the older single-notes field is still expected."""
    covers = q.get("covers") or []
    if covers:
        return " ".join(c.rstrip(".") + "." for c in covers)
    return (q.get("expected_answer_notes") or "").strip()


# ------------------------------------------------------------------- files
def question_path(q: dict) -> Path:
    return QUESTIONS_DIR / q["domain"] / q["topic"] / f"{q['id']}.md"


def save_question(q: dict) -> Path:
    _validate(q)
    path = question_path(q)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_question(q), encoding="utf-8")
    invalidate()
    return path


def delete_question(qid: str) -> bool:
    q = get(qid)
    if not q:
        return False
    question_path(q).unlink(missing_ok=True)
    invalidate()
    return True


def next_id(domain: str, topic: str) -> str:
    """Continuous numbering per topic, like ne-routing-007. Never reuses a number."""
    prefix = f"{domain}-{topic}-"
    n = 0
    for q in load_all():
        if q["id"].startswith(prefix):
            try:
                n = max(n, int(q["id"][len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{n + 1:03d}"


# ------------------------------------------------------------------- cache
_cache: dict = {"sig": None, "items": []}


def _signature() -> tuple:
    if not QUESTIONS_DIR.exists():
        return (0, 0)
    n, latest = 0, 0.0
    for root, _dirs, files in os.walk(QUESTIONS_DIR):
        for f in files:
            if f.endswith(".md"):
                n += 1
                latest = max(latest, os.stat(os.path.join(root, f)).st_mtime)
    return (n, latest)


def invalidate() -> None:
    _cache["sig"] = None


def load_all() -> list[dict]:
    sig = _signature()
    if _cache["sig"] == sig:
        return _cache["items"]
    items, errors = [], []
    for path in sorted(QUESTIONS_DIR.rglob("*.md")):
        try:
            items.append(parse_question(path.read_text(encoding="utf-8"), path))
        except Exception as exc:  # noqa: BLE001 — one bad file must not hide the bank
            errors.append(f"{path.relative_to(QUESTIONS_DIR)}: {exc}")
    _cache.update(sig=sig, items=items, errors=errors)
    return items


def load_errors() -> list[str]:
    load_all()
    return list(_cache.get("errors") or [])


def get(qid: str) -> dict | None:
    return next((q for q in load_all() if q["id"] == qid), None)


# ----------------------------------------------------------------- helpers
def _validate(q: dict, path: Path | None = None) -> None:
    where = f"{path}: " if path else ""
    if not _ID_RE.match(q.get("id") or ""):
        raise ValueError(f"{where}bad or missing id {q.get('id')!r}")
    if q.get("domain") not in config.DOMAINS:
        raise ValueError(f"{where}unknown domain {q.get('domain')!r}")
    if q.get("topic") not in config.TOPICS[q["domain"]]:
        raise ValueError(f"{where}unknown topic {q.get('topic')!r} for {q['domain']}")
    if q.get("difficulty") not in config.DIFFICULTIES:
        raise ValueError(f"{where}bad difficulty {q.get('difficulty')!r}")
    if not (q.get("prompt") or "").strip():
        raise ValueError(f"{where}empty prompt")
    if not q.get("covers") and not (q.get("expected_answer_notes") or "").strip():
        raise ValueError(f"{where}needs a 'Strong answer covers' section")


def _as_date(v) -> date:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except (TypeError, ValueError):
        return date.today()


def _as_list(chunk: str) -> list[str]:
    out = []
    for line in chunk.splitlines():
        s = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line).strip()
        if s:
            out.append(s)
    return out


_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def clean_item(text) -> str:
    """Strip a leading list marker ("- ", "3. ") so numbering never doubles up."""
    return _MARKER.sub("", str(text or "").strip()).strip()


def _bullets(items) -> str:
    return "\n".join(f"- {clean_item(i)}" for i in (items or []) if clean_item(i))


def _numbered(items) -> str:
    return "\n".join(f"{n}. {clean_item(i)}"
                     for n, i in enumerate((i for i in (items or []) if clean_item(i)), 1))
