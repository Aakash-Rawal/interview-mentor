"""Schema — idempotent on boot.

Every statement is CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS so
init_db() is safe to call on every startup and on an existing database.

Tables
  users                  one row per learner: profile + preferences
  conversations          tutor chats, one per (domain, topic) session
  conversation_messages  turns inside a conversation
  mocks                  mock interviews: question, transcript, score — resumable
  resumes / applications resume lab (kept from the earlier build)
  scraped_questions      review queue: generated/scraped candidates until promoted to a file
  job_targets            one row per job being chased: resume + JD + the planner's analysis
  focus_areas            what to study for a job target; conversations/mocks point back at it

Earlier builds also created sessions / messages / scores; those are no longer
written or read and can be dropped by hand if present.
"""
from db.connection import get_cursor

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id             TEXT PRIMARY KEY,
        background     JSONB NOT NULL DEFAULT '{}',
        active_domains JSONB NOT NULL DEFAULT '["pe"]',
        target_roles   JSONB NOT NULL DEFAULT '{}',
        interview_date DATE,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_domain TEXT NOT NULL DEFAULT 'pe'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS model TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id),
        domain      TEXT NOT NULL,
        topic       TEXT NOT NULL,
        title       TEXT NOT NULL DEFAULT 'New session',
        archived    BOOLEAN NOT NULL DEFAULT FALSE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id              SERIAL PRIMARY KEY,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS conversation_messages_conv_idx "
    "ON conversation_messages (conversation_id, id)",
    """
    CREATE TABLE IF NOT EXISTS mocks (
        id           SERIAL PRIMARY KEY,
        user_id      TEXT NOT NULL REFERENCES users(id),
        domain       TEXT NOT NULL,
        topic        TEXT NOT NULL,
        question_id  TEXT NOT NULL,
        question     JSONB NOT NULL,
        difficulty   TEXT NOT NULL DEFAULT 'medium',
        hints        BOOLEAN NOT NULL DEFAULT FALSE,
        status       TEXT NOT NULL DEFAULT 'active',   -- active | finished | abandoned
        transcript   JSONB NOT NULL DEFAULT '[]',
        score        JSONB,
        total        NUMERIC,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at  TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS mocks_user_status_idx ON mocks (user_id, status, created_at DESC)",
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
    """
    CREATE TABLE IF NOT EXISTS scraped_questions (
        id              SERIAL PRIMARY KEY,
        source          TEXT NOT NULL,
        source_id       TEXT,
        domain          TEXT NOT NULL,
        topic           TEXT NOT NULL,
        difficulty      TEXT NOT NULL DEFAULT 'medium',
        tags            JSONB NOT NULL DEFAULT '[]',
        prompt          TEXT NOT NULL,
        expected_answer_notes TEXT NOT NULL DEFAULT '',
        approved        BOOLEAN NOT NULL DEFAULT FALSE,
        raw_text        TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (source, source_id)
    )
    """,
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS quality_score INTEGER",
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS look_for JSONB NOT NULL DEFAULT '[]'",
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS covers JSONB NOT NULL DEFAULT '[]'",
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS follow_ups JSONB NOT NULL DEFAULT '[]'",
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS sample_answer TEXT",
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS companies JSONB NOT NULL DEFAULT '[]'",
    "ALTER TABLE scraped_questions ADD COLUMN IF NOT EXISTS promoted_id TEXT",
    """
    CREATE TABLE IF NOT EXISTS job_targets (
        id             SERIAL PRIMARY KEY,
        user_id        TEXT NOT NULL REFERENCES users(id),
        company        TEXT NOT NULL DEFAULT '',
        role           TEXT NOT NULL DEFAULT '',
        domain         TEXT NOT NULL DEFAULT 'pe',
        seniority      TEXT NOT NULL DEFAULT '',
        jd_text        TEXT NOT NULL,
        resume_id      INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
        interview_date DATE,
        status         TEXT NOT NULL DEFAULT 'active',   -- active | archived
        summary        TEXT NOT NULL DEFAULT '',
        strengths      JSONB NOT NULL DEFAULT '[]',
        unmapped       JSONB NOT NULL DEFAULT '[]',
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS job_targets_user_idx "
    "ON job_targets (user_id, status, updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS focus_areas (
        id         SERIAL PRIMARY KEY,
        target_id  INTEGER NOT NULL REFERENCES job_targets(id) ON DELETE CASCADE,
        title      TEXT NOT NULL,
        topic      TEXT NOT NULL,
        level      TEXT NOT NULL DEFAULT 'concept',  -- tool | concept
        priority   INTEGER NOT NULL DEFAULT 5,
        why_jd     TEXT NOT NULL DEFAULT '',
        gap        TEXT NOT NULL DEFAULT '',
        keywords   JSONB NOT NULL DEFAULT '[]',
        status     TEXT NOT NULL DEFAULT 'todo',     -- todo | studying | ready
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS focus_areas_target_idx ON focus_areas (target_id, priority)",
    # Study done against a plan is tagged, so plan progress is a query, not bookkeeping.
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS focus_id INTEGER "
    "REFERENCES focus_areas(id) ON DELETE SET NULL",
    "ALTER TABLE mocks ADD COLUMN IF NOT EXISTS focus_id INTEGER "
    "REFERENCES focus_areas(id) ON DELETE SET NULL",
]


def init_db() -> None:
    """Create or upgrade all tables. Safe to call on every boot."""
    with get_cursor(commit=True) as cur:
        for statement in SCHEMA:
            cur.execute(statement)


def ensure_user(user_id: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                    (user_id,))
