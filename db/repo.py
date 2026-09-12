"""Data access for the web app. Every function opens its own cursor.

Rows come back as dicts (RealDictCursor). JSONB columns are returned already
decoded by psycopg2; on write we json.dumps explicitly.
"""
from __future__ import annotations

import json
from datetime import date

import config
from db.connection import get_cursor

# --------------------------------------------------------------------- users
def get_user(user_id: str) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute("INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (user_id,))
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return dict(cur.fetchone())


def update_user(user_id: str, *, background: dict | None = None,
                target_roles: dict | None = None, interview_date: date | None = ...,
                current_domain: str | None = None, model: str | None = ...) -> None:
    sets, vals = [], []
    if background is not None:
        sets.append("background = %s"); vals.append(json.dumps(background))
    if target_roles is not None:
        sets.append("target_roles = %s"); vals.append(json.dumps(target_roles))
    if interview_date is not ...:
        sets.append("interview_date = %s"); vals.append(interview_date)
    if current_domain is not None:
        sets.append("current_domain = %s"); vals.append(current_domain)
    if model is not ...:
        sets.append("model = %s"); vals.append(model)
    if not sets:
        return
    sets.append("updated_at = now()")
    vals.append(user_id)
    with get_cursor(commit=True) as cur:
        cur.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = %s", vals)


# ------------------------------------------------------------- conversations
def create_conversation(user_id: str, domain: str, topic: str, title: str,
                        focus_id: int | None = None) -> int:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO conversations (user_id, domain, topic, title, focus_id) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, domain, topic, title, focus_id))
        return cur.fetchone()["id"]


def get_conversation(conv_id: int, user_id: str) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM conversations WHERE id = %s AND user_id = %s",
                    (conv_id, user_id))
        row = cur.fetchone()
        return dict(row) if row else None


def list_conversations(user_id: str, domain: str | None = None, topic: str | None = None,
                       limit: int = 50) -> list[dict]:
    sql = ("SELECT c.*, (SELECT count(*) FROM conversation_messages m "
           "WHERE m.conversation_id = c.id) AS message_count "
           "FROM conversations c WHERE c.user_id = %s AND NOT c.archived")
    vals: list = [user_id]
    if domain:
        sql += " AND c.domain = %s"; vals.append(domain)
    if topic:
        sql += " AND c.topic = %s"; vals.append(topic)
    sql += " ORDER BY c.updated_at DESC LIMIT %s"
    vals.append(limit)
    with get_cursor() as cur:
        cur.execute(sql, vals)
        return [dict(r) for r in cur.fetchall()]


def rename_conversation(conv_id: int, title: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE conversations SET title = %s, updated_at = now() WHERE id = %s",
                    (title[:120], conv_id))


def archive_conversation(conv_id: int, user_id: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE conversations SET archived = TRUE, updated_at = now() "
                    "WHERE id = %s AND user_id = %s", (conv_id, user_id))


def list_messages(conv_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT id, role, content, created_at FROM conversation_messages "
                    "WHERE conversation_id = %s ORDER BY id", (conv_id,))
        return [dict(r) for r in cur.fetchall()]


def add_message(conv_id: int, role: str, content: str) -> int:
    with get_cursor(commit=True) as cur:
        cur.execute("INSERT INTO conversation_messages (conversation_id, role, content) "
                    "VALUES (%s, %s, %s) RETURNING id", (conv_id, role, content))
        new_id = cur.fetchone()["id"]
        cur.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conv_id,))
        return new_id


# --------------------------------------------------------------------- mocks
def create_mock(user_id: str, domain: str, topic: str, question: dict,
                difficulty: str, hints: bool, focus_id: int | None = None) -> int:
    transcript = [{"role": "assistant", "content": question["prompt"]}]
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO mocks (user_id, domain, topic, question_id, question, difficulty, "
            "hints, transcript, focus_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (user_id, domain, topic, question["id"], json.dumps(question, default=str), difficulty,
             hints, json.dumps(transcript), focus_id))
        return cur.fetchone()["id"]


def get_mock(mock_id: int, user_id: str) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM mocks WHERE id = %s AND user_id = %s", (mock_id, user_id))
        row = cur.fetchone()
        return _mock_row(row) if row else None


def get_active_mock(user_id: str) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM mocks WHERE user_id = %s AND status = 'active' "
                    "ORDER BY created_at DESC LIMIT 1", (user_id,))
        row = cur.fetchone()
        return _mock_row(row) if row else None


def list_mocks(user_id: str, status: str | None = "finished", domain: str | None = None,
               limit: int = 20) -> list[dict]:
    sql = "SELECT * FROM mocks WHERE user_id = %s"
    vals: list = [user_id]
    if status:
        sql += " AND status = %s"; vals.append(status)
    if domain:
        sql += " AND domain = %s"; vals.append(domain)
    sql += " ORDER BY created_at DESC LIMIT %s"
    vals.append(limit)
    with get_cursor() as cur:
        cur.execute(sql, vals)
        return [_mock_row(r) for r in cur.fetchall()]


def append_mock_turns(mock_id: int, turns: list[dict]) -> None:
    """Append turns to the transcript. Single-user app: read-modify-write is fine."""
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT transcript FROM mocks WHERE id = %s FOR UPDATE", (mock_id,))
        transcript = list(cur.fetchone()["transcript"] or [])
        transcript.extend(turns)
        cur.execute("UPDATE mocks SET transcript = %s WHERE id = %s",
                    (json.dumps(transcript), mock_id))


def finish_mock(mock_id: int, score: dict) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE mocks SET status = 'finished', score = %s, total = %s, "
            "finished_at = now() WHERE id = %s",
            (json.dumps(score), score.get("total"), mock_id))


def abandon_mock(mock_id: int, user_id: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE mocks SET status = 'abandoned', finished_at = now() "
                    "WHERE id = %s AND user_id = %s AND status = 'active'", (mock_id, user_id))


def covered_question_ids(user_id: str) -> set[str]:
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT question_id FROM mocks WHERE user_id = %s "
                    "AND status IN ('finished', 'active')", (user_id,))
        return {r["question_id"] for r in cur.fetchall()}


def _mock_row(row) -> dict:
    d = dict(row)
    if d.get("total") is not None:
        d["total"] = float(d["total"])
    return d


# --------------------------------------------------------------- performance
def performance_summary(user_id: str) -> dict:
    """Per-domain, per-topic stats from finished mocks.

    Returns {domain: {topic: {"count", "avg", "last", "prev_avg",
                              "dimensions": {name: avg}, "top_fixes": [...]}}}
    """
    with get_cursor() as cur:
        cur.execute("SELECT domain, topic, total, score, finished_at FROM mocks "
                    "WHERE user_id = %s AND status = 'finished' AND total IS NOT NULL "
                    "ORDER BY finished_at", (user_id,))
        rows = [dict(r) for r in cur.fetchall()]

    out: dict = {}
    for r in rows:
        t = out.setdefault(r["domain"], {}).setdefault(r["topic"], {
            "totals": [], "dims": {}, "top_fixes": []})
        t["totals"].append(float(r["total"]))
        score = r["score"] or {}
        for dim, detail in (score.get("dimensions") or {}).items():
            try:
                t["dims"].setdefault(dim, []).append(float(detail.get("score")))
            except (TypeError, ValueError):
                pass
        if score.get("top_fix"):
            t["top_fixes"].append(score["top_fix"])

    for domain, topics in out.items():
        for topic, t in topics.items():
            totals = t.pop("totals")
            dims = t.pop("dims")
            prev = totals[:-1]
            t["count"] = len(totals)
            t["avg"] = round(sum(totals) / len(totals), 1)
            t["last"] = totals[-1]
            t["prev_avg"] = round(sum(prev) / len(prev), 1) if prev else None
            t["dimensions"] = {d: round(sum(v) / len(v), 1) for d, v in dims.items() if v}
            t["top_fixes"] = t["top_fixes"][-3:]
    return out


def weak_dimensions(summary: dict, domain: str, limit: int = 5) -> list[dict]:
    """Lowest-scoring rubric dimensions across a domain, from performance_summary()."""
    rows = []
    for topic, t in summary.get(domain, {}).items():
        for dim, avg in t.get("dimensions", {}).items():
            rows.append({"topic": topic, "dimension": dim, "avg": avg})
    rows.sort(key=lambda r: r["avg"])
    return rows[:limit]


def activity_counts(user_id: str) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM conversations WHERE user_id = %s AND NOT archived",
                    (user_id,))
        conversations = cur.fetchone()["n"]
        cur.execute("SELECT status, count(*) AS n FROM mocks WHERE user_id = %s GROUP BY status",
                    (user_id,))
        mocks = {r["status"]: r["n"] for r in cur.fetchall()}
    return {"conversations": conversations, "mocks": mocks}


# ---------------------------------------------------------- question review
CANDIDATE_LIST_FIELDS = ("tags", "look_for", "covers", "follow_ups", "companies")


def existing_prompts(topic: str | None = None) -> list[str]:
    """Every prompt known for a topic: bank files + pending candidates."""
    from question_bank import store
    prompts = [q["prompt"] for q in store.load_all() if not topic or q["topic"] == topic]
    with get_cursor() as cur:
        if topic:
            cur.execute("SELECT prompt FROM scraped_questions WHERE NOT approved AND topic = %s",
                        (topic,))
        else:
            cur.execute("SELECT prompt FROM scraped_questions WHERE NOT approved")
        prompts.extend(r["prompt"] for r in cur.fetchall())
    return prompts


def insert_candidates(rows: list[dict]) -> int:
    n = 0
    with get_cursor(commit=True) as cur:
        for r in rows:
            cur.execute(
                "INSERT INTO scraped_questions (source, source_id, domain, topic, difficulty, "
                "tags, prompt, expected_answer_notes, approved, raw_text, quality_score, "
                "look_for, covers, follow_ups, sample_answer, companies) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (source, source_id) DO NOTHING",
                (r["source"], r["source_id"], r["domain"], r["topic"], r["difficulty"],
                 json.dumps(r.get("tags") or []), r["prompt"], r.get("expected_answer_notes") or "",
                 bool(r.get("approved")), r.get("raw_text"), r.get("quality_score"),
                 json.dumps(r.get("look_for") or []), json.dumps(r.get("covers") or []),
                 json.dumps(r.get("follow_ups") or []), r.get("sample_answer"),
                 json.dumps(r.get("companies") or [])))
            n += cur.rowcount
    return n


def get_candidate(cid: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM scraped_questions WHERE id = %s", (cid,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_candidates(domain: str | None = None, approved: bool = False) -> list[dict]:
    sql = "SELECT * FROM scraped_questions WHERE approved = %s"
    vals: list = [approved]
    if domain:
        sql += " AND domain = %s"; vals.append(domain)
    sql += " ORDER BY topic, quality_score DESC NULLS LAST, id"
    with get_cursor() as cur:
        cur.execute(sql, vals)
        return [dict(r) for r in cur.fetchall()]


def pending_counts() -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT domain, count(*) AS n FROM scraped_questions "
                    "WHERE NOT approved GROUP BY domain")
        return {r["domain"]: r["n"] for r in cur.fetchall()}


def update_candidate(cid: int, **fields) -> None:
    sets, vals = [], []
    for k, v in fields.items():
        if k in CANDIDATE_LIST_FIELDS:
            v = json.dumps(list(v or []))
        sets.append(f"{k} = %s"); vals.append(v)
    if not sets:
        return
    vals.append(cid)
    with get_cursor(commit=True) as cur:
        cur.execute(f"UPDATE scraped_questions SET {', '.join(sets)} WHERE id = %s", vals)


def mark_promoted(cid: int, qid: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE scraped_questions SET approved = TRUE, promoted_id = %s WHERE id = %s",
                    (qid, cid))


def unmark_promoted(qid: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE scraped_questions SET approved = FALSE, promoted_id = NULL "
                    "WHERE promoted_id = %s", (qid,))


def delete_candidate(cid: int) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM scraped_questions WHERE id = %s", (cid,))


# ------------------------------------------------------------------- resumes
def save_resume(user_id: str, content_text: str, file_name: str | None = None,
                is_base: bool = True) -> int:
    """Store a resume. The base resume is what new job plans use by default."""
    with get_cursor(commit=True) as cur:
        if is_base:
            cur.execute("UPDATE resumes SET is_base = FALSE WHERE user_id = %s", (user_id,))
        cur.execute("INSERT INTO resumes (user_id, file_name, content_text, is_base) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (user_id, file_name, content_text, is_base))
        return cur.fetchone()["id"]


def get_base_resume(user_id: str) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM resumes WHERE user_id = %s "
                    "ORDER BY is_base DESC, uploaded_at DESC LIMIT 1", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


# --------------------------------------------------------------- job targets
def create_target(user_id: str, *, jd_text: str, company: str = "", role: str = "",
                  domain: str = "pe", seniority: str = "", resume_id: int | None = None,
                  interview_date: date | None = None, summary: str = "",
                  strengths: list | None = None, unmapped: list | None = None) -> int:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO job_targets (user_id, company, role, domain, seniority, jd_text, "
            "resume_id, interview_date, summary, strengths, unmapped) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, company, role, domain, seniority, jd_text, resume_id, interview_date,
             summary, json.dumps(strengths or []), json.dumps(unmapped or [])))
        return cur.fetchone()["id"]


def get_target(target_id: int, user_id: str) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM job_targets WHERE id = %s AND user_id = %s",
                    (target_id, user_id))
        row = cur.fetchone()
        return dict(row) if row else None


def list_targets(user_id: str, status: str | None = "active", limit: int = 30) -> list[dict]:
    """Job targets with plan progress rolled up from their focus areas."""
    sql = ("SELECT t.*, "
           "(SELECT count(*) FROM focus_areas f WHERE f.target_id = t.id) AS focus_count, "
           "(SELECT count(*) FROM focus_areas f WHERE f.target_id = t.id "
           " AND f.status = 'ready') AS ready_count, "
           "(SELECT round(avg(m.total), 1) FROM mocks m JOIN focus_areas f ON f.id = m.focus_id "
           " WHERE f.target_id = t.id AND m.status = 'finished' AND m.total IS NOT NULL) AS avg_total "
           "FROM job_targets t WHERE t.user_id = %s")
    vals: list = [user_id]
    if status:
        sql += " AND t.status = %s"; vals.append(status)
    sql += " ORDER BY t.interview_date NULLS LAST, t.updated_at DESC LIMIT %s"
    vals.append(limit)
    with get_cursor() as cur:
        cur.execute(sql, vals)
        return [_target_row(r) for r in cur.fetchall()]


def set_target_status(target_id: int, user_id: str, status: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE job_targets SET status = %s, updated_at = now() "
                    "WHERE id = %s AND user_id = %s", (status, target_id, user_id))


def delete_target(target_id: int, user_id: str) -> None:
    """Focus areas cascade; conversations and mocks survive with focus_id set NULL."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM job_targets WHERE id = %s AND user_id = %s",
                    (target_id, user_id))


def _target_row(row) -> dict:
    d = dict(row)
    if d.get("avg_total") is not None:
        d["avg_total"] = float(d["avg_total"])
    return d


# --------------------------------------------------------------- focus areas
def add_focus_areas(target_id: int, areas: list[dict]) -> int:
    with get_cursor(commit=True) as cur:
        for a in areas:
            cur.execute(
                "INSERT INTO focus_areas (target_id, title, topic, level, priority, why_jd, "
                "gap, keywords) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (target_id, a["title"], a["topic"], a.get("level") or "concept",
                 a.get("priority") or 5, a.get("why_jd") or "", a.get("gap") or "",
                 json.dumps(list(a.get("keywords") or []))))
    return len(areas)


def list_focus_areas(target_id: int) -> list[dict]:
    """Focus areas with the study done against each one."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT f.*, "
            "(SELECT count(*) FROM mocks m WHERE m.focus_id = f.id "
            " AND m.status = 'finished') AS mock_count, "
            "(SELECT round(avg(m.total), 1) FROM mocks m WHERE m.focus_id = f.id "
            " AND m.status = 'finished' AND m.total IS NOT NULL) AS avg_total, "
            "(SELECT count(*) FROM conversations c WHERE c.focus_id = f.id "
            " AND NOT c.archived) AS chat_count "
            "FROM focus_areas f WHERE f.target_id = %s ORDER BY f.priority, f.id", (target_id,))
        return [_focus_row(r) for r in cur.fetchall()]


def get_focus(focus_id: int, user_id: str) -> dict | None:
    """A focus area joined with its job target. None if it is not this user's."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT f.*, t.company, t.role, t.domain, t.seniority, t.interview_date, "
            "t.id AS target_id, t.jd_text FROM focus_areas f "
            "JOIN job_targets t ON t.id = f.target_id "
            "WHERE f.id = %s AND t.user_id = %s", (focus_id, user_id))
        row = cur.fetchone()
        return _focus_row(row) if row else None


def _focus_row(row) -> dict:
    """A focus area's domain comes from its topic, not from its plan.

    A production engineering plan can legitimately hold a routing focus area; studying it
    has to use the network engineering domain or the topic would not resolve.
    """
    d = _target_row(row)
    d["domain"] = config.domain_for_topic(d["topic"]) or d.get("domain") or "pe"
    return d


def set_focus_status(focus_id: int, user_id: str, status: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE focus_areas SET status = %s WHERE id = %s AND target_id IN "
            "(SELECT id FROM job_targets WHERE user_id = %s)", (status, focus_id, user_id))
