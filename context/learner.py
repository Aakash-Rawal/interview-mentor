"""LearnerContext — what every agent knows about the learner for this request.

The earlier build kept one mutable SharedContext object alive for the whole
process. In a web app each request builds a fresh, read-only snapshot from the
database: profile, performance history, and prior study sessions. Agents read
it to personalise prompts; they never mutate it. Persistence goes through
db.repo, so nothing is lost on refresh or restart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import config
from db import repo


@dataclass
class LearnerContext:
    user_id: str
    domain: str
    topic: str
    model: str
    background: dict = field(default_factory=dict)
    target_role: str = ""
    interview_date: date | None = None
    performance: dict = field(default_factory=dict)      # this domain: {topic: stats}
    prior_sessions: list[dict] = field(default_factory=list)  # tutor chats on this topic

    # ---- derived -----------------------------------------------------
    @property
    def domain_label(self) -> str:
        return config.DOMAINS.get(self.domain, self.domain)

    @property
    def topic_label(self) -> str:
        return config.topic_label(self.topic)

    def days_to_interview(self) -> int | None:
        if not self.interview_date:
            return None
        return (self.interview_date - date.today()).days

    # ---- prompt fragments -------------------------------------------
    def profile_text(self) -> str:
        bits = []
        exp = self.background.get("experience")
        if exp:
            bits.append(f"Experience: {exp}.")
        lang = self.background.get("language")
        if lang:
            bits.append(f"Preferred programming language: {lang}.")
        if self.target_role:
            bits.append(f"Target role: {self.target_role}.")
        days = self.days_to_interview()
        if days is not None:
            when = ("today" if days == 0 else f"in {days} days" if days > 0
                    else f"{-days} days ago")
            bits.append(f"Interview is {when}.")
        notes = self.background.get("notes")
        if notes:
            bits.append(f"Learner notes: {notes}")
        return " ".join(bits) or "No profile yet — ask about their level if it matters."

    def performance_text(self) -> str:
        if not self.performance:
            return "No scored mocks yet in this domain."
        lines = []
        for topic, t in self.performance.items():
            dims = t.get("dimensions", {})
            weakest = sorted(dims.items(), key=lambda kv: kv[1])[:2]
            weak_txt = (", weakest: " + ", ".join(f"{d} {s}/10" for d, s in weakest)
                        if weakest else "")
            lines.append(f"- {config.topic_label(topic)}: {t['count']} mock(s), "
                         f"avg {t['avg']}/10, last {t['last']}/10{weak_txt}")
            for fix in t.get("top_fixes", [])[-2:]:
                lines.append(f"    previous feedback: {fix}")
        return "\n".join(lines)

    def prior_sessions_text(self) -> str:
        if not self.prior_sessions:
            return "None yet."
        return "\n".join(f"- {s['title']} ({s['created_at']:%b %d})"
                         for s in self.prior_sessions[:8])


def build_context(user_id: str, domain: str, topic: str,
                  exclude_conversation: int | None = None) -> LearnerContext:
    user = repo.get_user(user_id)
    summary = repo.performance_summary(user_id)
    sessions = [s for s in repo.list_conversations(user_id, domain=domain, topic=topic, limit=10)
                if s["id"] != exclude_conversation and s["message_count"] > 0]
    return LearnerContext(
        user_id=user_id,
        domain=domain,
        topic=topic,
        model=user.get("model") or config.DEFAULT_MODEL,
        background=user.get("background") or {},
        target_role=(user.get("target_roles") or {}).get(domain, ""),
        interview_date=user.get("interview_date"),
        performance=summary.get(domain, {}),
        prior_sessions=sessions,
    )
