"""Orchestrator — the only agent main.py talks to directly.

Classifies intent, maintains current_domain / current_topic on the SharedContext,
and routes to the Tutor or Interviewer. Owns the ResumeAgent for the resume flow.
Phase 1 uses lightweight keyword classification (Phase 4 makes it proactive).
"""
from agents.tutor import Tutor
from agents.interviewer import Interviewer
from agents.resume_agent import ResumeAgent
from context.shared_context import SharedContext
import config

# Keyword → topic, so "let's do bgp" sets the routing topic.
_TOPIC_KEYWORDS = {
    "coding": "coding", "code": "coding", "algorithm": "coding",
    "linux": "linux", "command": "linux",
    "troubleshoot": "troubleshooting", "debug": "troubleshooting", "incident": "troubleshooting",
    "system design": "system_design", "design a": "system_design", "architecture": "system_design",
    "subnet": "networking_fundamentals", "tcp": "networking_fundamentals",
    "osi": "networking_fundamentals", "vlan": "networking_fundamentals",
    "bgp": "routing", "ospf": "routing", "routing": "routing", "route": "routing",
    "network troubleshoot": "network_troubleshooting", "packet": "network_troubleshooting",
    "traceroute": "network_troubleshooting", "tcpdump": "network_troubleshooting",
    "spine": "network_design", "datacenter": "network_design", "vpc": "network_design",
    "firewall": "network_security", "acl": "network_security", "vpn": "network_security",
}


class Orchestrator:
    def __init__(self):
        self.tutor = Tutor()
        self.interviewer = Interviewer()
        self.resume = ResumeAgent()

    def route(self, ctx: SharedContext, user_input: str) -> str:
        text = user_input.strip()
        low = text.lower()

        # 1. If a mock is running, the Interviewer owns the turn.
        if self.interviewer.active:
            if low in {"done", "finish", "stop", "score me", "end mock"}:
                return self._render_score(self.interviewer.finish_mock(ctx))
            return self.interviewer.turn(ctx, text)

        # 2. Domain switch.
        if self._maybe_switch_domain(ctx, low):
            label = config.DOMAINS.get(ctx.current_domain, ctx.current_domain)
            return (f"Switched to **{label}**. Topics: "
                    f"{', '.join(config.TOPICS[ctx.current_domain])}. "
                    f"Ask a question to learn, or say 'start a mock'.")

        # 3. Topic detection (updates current_topic for both learn and mock).
        topic = self._detect_topic(ctx, low)
        if topic:
            ctx.current_topic = topic

        # 4. Progress check.
        if any(k in low for k in ("progress", "how am i doing", "my scores", "weak area")):
            return self._progress_summary(ctx)

        # 5. Start a mock.
        if any(k in low for k in ("start a mock", "mock me", "interview me", "quiz me",
                                  "start mock", "give me a question")):
            topic = ctx.current_topic or config.TOPICS[ctx.current_domain][0]
            ctx.current_topic = topic
            hints = "hint" in low
            return self.interviewer.start_mock(ctx, topic, hints=hints)

        # 6. Default: tutoring.
        if not ctx.current_topic:
            ctx.current_topic = config.TOPICS[ctx.current_domain][0]
        return self.tutor.respond(ctx, text)

    # ---- resume flow (invoked directly by main.py with collected inputs) ----
    def run_resume(self, ctx: SharedContext, mode: str, resume_text: str,
                   jd_text: str, tone: str | None = None):
        if mode == "analyze":
            return self.resume.analyze(ctx, resume_text, jd_text)
        if mode == "tailor":
            return self.resume.tailor(ctx, resume_text, jd_text)
        if mode == "cover_letter":
            return self.resume.cover_letter(ctx, resume_text, jd_text,
                                            tone or "confident and professional")
        return {"error": f"Unknown resume mode: {mode}"}

    # ---- helpers ----
    @staticmethod
    def _maybe_switch_domain(ctx: SharedContext, low: str) -> bool:
        if any(k in low for k in ("switch to network", "network engineering", "do network", "ne mode")):
            ctx.current_domain = "ne"
            ctx.current_topic = None
            return True
        if any(k in low for k in ("switch to pe", "production engineering", "sre mode", "pe mode")):
            ctx.current_domain = "pe"
            ctx.current_topic = None
            return True
        return False

    @staticmethod
    def _detect_topic(ctx: SharedContext, low: str) -> str | None:
        valid = set(config.TOPICS[ctx.current_domain])
        for kw, topic in _TOPIC_KEYWORDS.items():
            if kw in low and topic in valid:
                return topic
        return None

    @staticmethod
    def _progress_summary(ctx: SharedContext) -> str:
        data = ctx.performance_data
        if not data:
            return "No mock scores yet. Say 'start a mock' to get your first score."
        lines = ["**Your progress so far:**"]
        for domain, topics in data.items():
            lines.append(f"\n_{config.DOMAINS.get(domain, domain)}_")
            for topic, scores in topics.items():
                totals = [s.get("total") for s in scores if s.get("total") is not None]
                avg = round(sum(totals) / len(totals), 1) if totals else "n/a"
                lines.append(f"  • {topic}: {len(scores)} mock(s), avg {avg}/10")
        return "\n".join(lines)

    @staticmethod
    def _render_score(score: dict) -> str:
        if "error" in score:
            return f"Scoring problem: {score['error']}"
        lines = [f"\n**Mock complete — {score.get('topic')}** | "
                 f"Total: **{score.get('total')}/10**\n"]
        for dim, detail in score.get("dimensions", {}).items():
            lines.append(f"  • {dim}: {detail.get('score')}/10 — {detail.get('note')}")
        lines.append(f"\n**Summary:** {score.get('summary', '')}")
        lines.append(f"**Top fix:** {score.get('top_fix', '')}")
        return "\n".join(lines)
