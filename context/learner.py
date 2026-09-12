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
    focus: dict | None = None    # focus_areas row joined with its job target, when studying a plan

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

    @property
    def job_label(self) -> str:
        """'Staff Production Engineer at Cloudflare' for the current plan, else ''."""
        if not self.focus:
            return ""
        role = (self.focus.get("role") or "").strip()
        company = (self.focus.get("company") or "").strip()
        if role and company:
            return f"{role} at {company}"
        return role or company

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

    def focus_text(self) -> str:
        """Prompt block for the job plan this session belongs to. '' for general study.

        The `level` distinction is the point of this block. A job description asking for
        Kubernetes is hiring someone who can run it, so a tool-level focus area is taught
        and probed at usage level; only a concept-level one goes after the mechanism
        underneath. The topic still supplies the reference material and the rubric.
        """
        f = self.focus
        if not f:
            return ""
        lines = ["## This session is part of a job-specific prep plan",
                 "This is preparation for one real job, not general study."]
        if self.job_label:
            lines.append(f"The job: {self.job_label}.")
        lines.append(f'Focus area: "{f.get("title")}" '
                     f'(practice material: {self.topic_label}).')
        if f.get("why_jd"):
            lines.append(f"What the job description asks for: {f['why_jd']}")
        if f.get("gap"):
            lines.append(f"Where they stand against it: {f['gap']}")
        keywords = [str(k) for k in (f.get("keywords") or [])]
        if keywords:
            lines.append("The job description's own vocabulary — use their words, not synonyms: "
                         + ", ".join(keywords) + ".")
        if f.get("level") == "tool":
            lines.append(
                "This is a tool or platform requirement, so pitch it where the job does: how to "
                "use and operate it well — the workflows, the settings that matter, the failure "
                "modes an operator actually hits, the trade-offs in applying it. Reach for the "
                "theory underneath only where it changes what they would do in practice.")
        else:
            lines.append(
                "This is a concept requirement, so go for real depth: the mechanism, why it "
                "behaves that way, and what breaks at the edges.")
        return "\n".join(lines)

    def prior_sessions_text(self) -> str:
        if not self.prior_sessions:
            return "None yet."
        return "\n".join(f"- {s['title']} ({s['created_at']:%b %d})"
                         for s in self.prior_sessions[:8])


def build_context(user_id: str, domain: str, topic: str,
                  exclude_conversation: int | None = None,
                  focus: dict | None = None) -> LearnerContext:
    """Snapshot for one request. `focus` is a repo.get_focus() row when the learner is
    working through a job plan; its role and interview date then win over the profile's."""
    user = repo.get_user(user_id)
    summary = repo.performance_summary(user_id)
    sessions = [s for s in repo.list_conversations(user_id, domain=domain, topic=topic, limit=10)
                if s["id"] != exclude_conversation and s["message_count"] > 0]
    target_role = (user.get("target_roles") or {}).get(domain, "")
    interview_date = user.get("interview_date")
    if focus:
        role = (focus.get("role") or "").strip()
        seniority = (focus.get("seniority") or "").strip()
        if seniority and seniority.lower() not in role.lower():
            role = f"{seniority} {role}".strip()      # "Staff Production Engineer", not "staff Staff …"
        company = (focus.get("company") or "").strip()
        target_role = (f"{role} at {company}" if role and company else role or company
                       or target_role)
        interview_date = focus.get("interview_date") or interview_date
    return LearnerContext(
        user_id=user_id,
        domain=domain,
        topic=topic,
        model=user.get("model") or config.DEFAULT_MODEL,
        background=user.get("background") or {},
        target_role=target_role,
        interview_date=interview_date,
        performance=summary.get(domain, {}),
        prior_sessions=sessions,
        focus=focus,
    )
