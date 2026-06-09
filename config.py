"""Central configuration. Everything imports from here.

Loads environment variables from .env and exposes typed constants the rest
of the app reads. Build order rule: this file has no internal dependencies.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Load .env from the project root, regardless of the working directory the
# CLI or UI was launched from.
load_dotenv(BASE_DIR / ".env")

# --- Secrets / connection ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/interview_prep")

# --- Model ---
# NOTE: corrected from the build plan's stale 'claude-sonnet-4-20250514'.
# Current Sonnet generation is claude-sonnet-4-6.
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-6")
MAX_TOKENS = 1500
# Resume tailoring / cover letters need more room than a tutoring reply.
MAX_TOKENS_LONG = 4000

# --- Domains -------------------------------------------------------------
# The platform is multi-domain. A user can prep for one or several at once.
DOMAINS = {
    "pe": "Production Engineering (Meta PE / SRE)",
    "ne": "Network Engineering",
}

# Topics available per domain. Drives skill-file loading and question filtering.
TOPICS = {
    "pe": ["coding", "linux", "troubleshooting", "system_design"],
    "ne": ["networking_fundamentals", "routing", "network_troubleshooting",
            "network_design", "network_security"],
}

# Maps a topic to the skill markdown file the Tutor/Interviewer prepend.
SKILL_FILES = {
    # PE
    "coding": "pe/coding_patterns.md",
    "linux": "pe/linux_commands.md",
    "troubleshooting": "pe/troubleshooting_framework.md",
    "system_design": "pe/system_design_concepts.md",
    # NE
    "networking_fundamentals": "ne/networking_fundamentals.md",
    "routing": "ne/routing_protocols.md",
    "network_troubleshooting": "ne/network_troubleshooting.md",
    "network_design": "ne/network_design.md",
    "network_security": "ne/network_security.md",
    # Resume
    "ats": "resume/ats_systems.md",
    "resume_writing": "resume/resume_writing.md",
    # Scraper — edit skills/scraper/extraction_focus.md to change what gets extracted
    "scraper_focus": "scraper/extraction_focus.md",
}


# --- Scraper ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "interview_mentor_scraper/1.0")

# Subreddits to mine for interview questions.
REDDIT_SUBREDDITS = ["sre", "devops", "networking", "linuxadmin", "ExperiencedDevs"]
# Search terms that surface real interview-experience posts.
REDDIT_SEARCH_TERMS = ["interview questions", "what were you asked", "interview experience",
                       "interview prep", "got the job", "failed the interview"]

# Stack Exchange sites + tags we scrape for real Q&A that doubles as interview fodder.
STACKEXCHANGE_SOURCES = [
    {"site": "serverfault",  "tags": ["networking", "linux", "bgp", "troubleshooting"]},
    {"site": "unix",         "tags": ["linux", "bash", "performance", "disk"]},
    {"site": "networkengineering", "tags": ["bgp", "ospf", "routing", "switching", "vpc"]},
]
# Only pull questions with at least this many upvotes (quality gate).
STACKEXCHANGE_MIN_SCORE = 5

# GitHub — personal access token gives 5k req/hr (vs 60 unauthenticated).
# Create one at https://github.com/settings/tokens (no scopes needed for public repos).
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Repos to mine for question content. Each entry is "owner/repo".
# File extensions to read from each repo (markdown only by default).
GITHUB_REPOS = [
    # Coding / algorithms / system design
    "donnemartin/system-design-primer",
    "checkcheckzz/system-design-interview",
    "alex/what-happens-when",
    "jwasham/coding-interview-university",
    "yangshun/tech-interview-handbook",
    # Networking / SRE / PE
    "mxssl/sre-interview-prep-guide",
    "michael-kehoe/sre-university",
    "bregman-arie/devops-exercises",
    "trimstray/the-book-of-secret-knowledge",
    "jlevy/the-art-of-command-line",
]
# Only read files with these extensions.
GITHUB_FILE_EXTENSIONS = {".md", ".rst", ".txt"}
# Skip files larger than this (bytes) to avoid ingesting huge reference docs.
GITHUB_MAX_FILE_BYTES = 150_000

# Hacker News — Algolia search API, no auth required.
# Search terms that surface interview/career/tech discussion threads on HN.
HN_SEARCH_TERMS = [
    "ask hn interview questions sre",
    "ask hn interview questions networking",
    "ask hn system design interview",
    "ask hn production engineer interview",
    "ask hn linux interview",
    "ask hn how to prepare sre interview",
]
# Only fetch HN items with at least this many points.
HN_MIN_POINTS = 10
# Max results per search term.
HN_MAX_RESULTS_PER_TERM = 20

# Auto-approve scraped questions that score at least this quality from Claude (0-10).
SCRAPER_AUTO_APPROVE_THRESHOLD = 7


def validate() -> list[str]:
    """Return a list of human-readable problems with the current config."""
    problems = []
    if not ANTHROPIC_API_KEY:
        problems.append("ANTHROPIC_API_KEY is not set (copy .env.example to .env).")
    if not DATABASE_URL:
        problems.append("DATABASE_URL is not set.")
    return problems
