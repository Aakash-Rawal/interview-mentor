"""SharedContext — the backbone every agent reads from and writes to.

This is what makes the platform feel like one coherent system instead of a
handful of isolated bots. It is serialised to/from JSON for PostgreSQL storage
(see db.models). Keep every field JSON-serialisable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date


@dataclass
class SharedContext:
    user_id: str

    # Who the user is: {"experience": "...", "language": "python", "weak_areas": [...]}
    user_background: dict = field(default_factory=dict)

    # Full conversation so far: [{"role": "user"|"assistant", "content": "..."}]
    session_history: list = field(default_factory=list)

    # What is being discussed right now (a topic key from config.TOPICS).
    current_topic: str | None = None

    # Drives urgency in prep plans. None until the user sets one.
    interview_date: date | None = None

    # Scores from past mocks, keyed by domain then topic.
    performance_data: dict = field(default_factory=dict)

    # --- Multi-domain (PE + NE) ---------------------------------------
    # Which domains the user is actively prepping for, e.g. ["pe", "ne"].
    active_domains: list = field(default_factory=lambda: ["pe"])
    # Target role per domain, e.g. {"pe": "Meta E4/E5", "ne": "Network Eng L5"}.
    target_roles: dict = field(default_factory=dict)
    # The domain currently in focus for routing.
    current_domain: str = "pe"

    # --- Resume / ATS agent -------------------------------------------
    base_resume_text: str | None = None      # stored once, reused per application
    resume_file_path: str | None = None
    active_jd: str | None = None             # current job description being targeted
    ats_keywords_found: list = field(default_factory=list)
    ats_keywords_missing: list = field(default_factory=list)

    # ---- Mutators every agent uses ----
    def add_exchange(self, role: str, content: str) -> None:
        self.session_history.append({"role": role, "content": content})

    def record_score(self, domain: str, topic: str, score: dict) -> None:
        self.performance_data.setdefault(domain, {}).setdefault(topic, []).append(score)

    # ---- (De)serialisation for PostgreSQL ----
    def to_json(self) -> str:
        data = asdict(self)
        if isinstance(self.interview_date, date):
            data["interview_date"] = self.interview_date.isoformat()
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: str | dict) -> "SharedContext":
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if data.get("interview_date"):
            data["interview_date"] = date.fromisoformat(data["interview_date"])
        # Drop unknown keys so old rows survive schema additions.
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in known})
