"""Central configuration. Everything imports from here; this file imports nothing internal.

Values come from .env (loaded from the project root regardless of the working
directory) with sensible defaults for a single-user local install.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# --- Paths ---------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

# --- Secrets / connection ------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/interview_prep")

# --- Web server ----------------------------------------------------------
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8765"))
# Single-user install. Override to keep test data separate from real data.
USER_ID = os.getenv("INTERVIEW_MENTOR_USER_ID", "local-user")

# --- Models --------------------------------------------------------------
# The user can switch models in Settings; this is the default for new installs.
DEFAULT_MODEL = os.getenv("MODEL_NAME", "claude-opus-5")
MODELS = {
    "claude-opus-5": "Claude Opus 5 — best reasoning, recommended for mocks",
    "claude-sonnet-5": "Claude Sonnet 5 — faster and cheaper, fine for tutoring",
}
MAX_TOKENS_CHAT = 8000       # streamed tutor / interviewer turns
MAX_TOKENS_LONG = 16000      # scoring, resume rewrites
MAX_TOKENS_BATCH = 48000     # question generation / enrichment (streamed)
EFFORT_CHAT = "medium"       # conversational turns: latency matters
EFFORT_SCORE = "high"        # rubric scoring: correctness matters

# --- Domains & topics ----------------------------------------------------
DOMAINS = {
    "pe": "Production Engineering / SRE",
    "ne": "Network Engineering",
}

TOPICS = {
    "pe": ["coding", "linux", "troubleshooting", "system_design"],
    "ne": ["networking_fundamentals", "routing", "network_troubleshooting",
           "network_design", "network_security"],
}

TOPIC_LABELS = {
    "coding": "Coding",
    "linux": "Linux internals",
    "troubleshooting": "Troubleshooting",
    "system_design": "System design",
    "networking_fundamentals": "Networking fundamentals",
    "routing": "Routing protocols",
    "network_troubleshooting": "Network troubleshooting",
    "network_design": "Network design",
    "network_security": "Network security",
}

DIFFICULTIES = ["easy", "medium", "hard"]

# --- Job plans -----------------------------------------------------------
# A plan is a short checklist, not a wishlist: the planner is capped here.
MAX_FOCUS_AREAS = 8
# "tool" = the JD hires for operating something (Kubernetes, Terraform); teach and probe
# at usage level. "concept" = the JD asks for the idea itself (BGP path selection).
FOCUS_LEVELS = ("tool", "concept")
FOCUS_STATUSES = ("todo", "studying", "ready")

# Topic -> skill markdown prepended to the Tutor / Interviewer system prompt.
SKILL_FILES = {
    "coding": "pe/coding_patterns.md",
    "linux": "pe/linux_commands.md",
    "troubleshooting": "pe/troubleshooting_framework.md",
    "system_design": "pe/system_design_concepts.md",
    "networking_fundamentals": "ne/networking_fundamentals.md",
    "routing": "ne/routing_protocols.md",
    "network_troubleshooting": "ne/network_troubleshooting.md",
    "network_design": "ne/network_design.md",
    "network_security": "ne/network_security.md",
    "ats": "resume/ats_systems.md",
    "resume_writing": "resume/resume_writing.md",
    "scraper_focus": "scraper/extraction_focus.md",
}


def topic_label(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("_", " ").title())


def domain_for_topic(topic: str) -> str | None:
    for domain, topics in TOPICS.items():
        if topic in topics:
            return domain
    return None


# --- Question-bank scraper (optional, needs API credentials) -------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "interview_mentor_scraper/1.0")
REDDIT_SUBREDDITS = ["sre", "devops", "networking", "linuxadmin", "ExperiencedDevs"]
REDDIT_SEARCH_TERMS = ["interview questions", "what were you asked", "interview experience",
                       "interview prep", "got the job", "failed the interview"]

STACKEXCHANGE_SOURCES = [
    {"site": "serverfault", "tags": ["networking", "linux", "bgp", "troubleshooting"]},
    {"site": "unix", "tags": ["linux", "bash", "performance", "disk"]},
    {"site": "networkengineering", "tags": ["bgp", "ospf", "routing", "switching", "vpc"]},
]
STACKEXCHANGE_MIN_SCORE = 5

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPOS = [
    "donnemartin/system-design-primer",
    "checkcheckzz/system-design-interview",
    "alex/what-happens-when",
    "jwasham/coding-interview-university",
    "yangshun/tech-interview-handbook",
    "mxssl/sre-interview-prep-guide",
    "michael-kehoe/sre-university",
    "bregman-arie/devops-exercises",
    "trimstray/the-book-of-secret-knowledge",
    "jlevy/the-art-of-command-line",
]
GITHUB_FILE_EXTENSIONS = {".md", ".rst", ".txt"}
GITHUB_MAX_FILE_BYTES = 150_000

HN_SEARCH_TERMS = [
    "ask hn interview questions sre",
    "ask hn interview questions networking",
    "ask hn system design interview",
    "ask hn production engineer interview",
    "ask hn linux interview",
    "ask hn how to prepare sre interview",
]
HN_MIN_POINTS = 10
HN_MAX_RESULTS_PER_TERM = 20
SCRAPER_AUTO_APPROVE_THRESHOLD = 7


def validate() -> list[str]:
    """Human-readable problems with the current configuration."""
    problems = []
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("sk-ant-..."):
        problems.append("ANTHROPIC_API_KEY is not set in .env")
    if not DATABASE_URL:
        problems.append("DATABASE_URL is not set in .env")
    return problems
