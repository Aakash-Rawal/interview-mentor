"""Table creation — idempotent on boot.

Every table uses CREATE TABLE IF NOT EXISTS so init_db() is safe to call on
every startup. Phase 1 tables plus the resume/ATS tables we added.
"""
from db.connection import get_cursor

SCHEMA = [
    # --- Core (Phase 1) ---
    """
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        background    JSONB NOT NULL DEFAULT '{}',
        active_domains JSONB NOT NULL DEFAULT '["pe"]',
        target_roles  JSONB NOT NULL DEFAULT '{}',
        interview_date DATE,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id),
        context     JSONB NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id          SERIAL PRIMARY KEY,
        session_id  INTEGER NOT NULL REFERENCES sessions(id),
        role        TEXT NOT NULL,
        content     TEXT NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scores (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id),
        domain      TEXT NOT NULL,
        topic       TEXT NOT NULL,
        question_id TEXT,
        rubric      JSONB NOT NULL,
        total       NUMERIC,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # --- Resume / ATS agent ---
    """
    CREATE TABLE IF NOT EXISTS resumes (
        id           SERIAL PRIMARY KEY,
        user_id      TEXT NOT NULL REFERENCES users(id),
        file_name    TEXT,
        content_text TEXT NOT NULL,
        is_base      BOOLEAN NOT NULL DEFAULT FALSE,
        uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS applications (
        id              SERIAL PRIMARY KEY,
        user_id         TEXT NOT NULL REFERENCES users(id),
        resume_id       INTEGER REFERENCES resumes(id),
        company         TEXT,
        role            TEXT,
        jd_text         TEXT NOT NULL,
        ats_score       NUMERIC,
        keywords_added  JSONB DEFAULT '[]',
        tailored_resume TEXT,
        cover_letter    TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
]


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call every boot."""
    with get_cursor(commit=True) as cur:
        for statement in SCHEMA:
            cur.execute(statement)


def ensure_user(user_id: str) -> None:
    """Make sure the parent users row exists before any child writes.

    scores/applications/sessions all FK to users(id); a mock can be scored
    mid-session, before the session is saved, so the user row must exist from
    the moment the session starts — not only at save time.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
            (user_id,))
