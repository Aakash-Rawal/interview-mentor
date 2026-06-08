"""Central configuration. Everything imports from here.

Loads environment variables from .env and exposes typed constants the rest
of the app reads. Build order rule: this file has no internal dependencies.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

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
}


def validate() -> list[str]:
    """Return a list of human-readable problems with the current config."""
    problems = []
    if not ANTHROPIC_API_KEY:
        problems.append("ANTHROPIC_API_KEY is not set (copy .env.example to .env).")
    if not DATABASE_URL:
        problems.append("DATABASE_URL is not set.")
    return problems
