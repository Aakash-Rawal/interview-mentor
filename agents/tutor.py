"""Tutor agent — explains concepts at the user's level.

Loads the relevant skill markdown for the current topic, prepends it to the
system prompt, adapts to user_background, and appends each exchange to
session_history on the shared context.
"""
from agents.base import load_skill, call_claude, stream_claude
from context.shared_context import SharedContext

SYSTEM = """You are an expert interview tutor for {domain}.
Explain concepts clearly and adapt to the learner's level.

Learner background: {background}

Use the reference material below as ground truth. Be concrete, use small
examples, and check understanding. Keep answers focused — this is interview
prep, not a textbook.

=== REFERENCE MATERIAL ({topic}) ===
{skill}
=== END REFERENCE ==="""


class Tutor:
    def _prepare(self, ctx: SharedContext, user_input: str) -> str:
        """Build the system prompt for the current topic and record the user turn."""
        topic = ctx.current_topic or "general"
        skill = load_skill(topic)
        domain = ctx.current_domain
        domain_label = {"pe": "Production Engineering / SRE",
                        "ne": "Network Engineering"}.get(domain, domain)
        system = SYSTEM.format(
            domain=domain_label,
            background=ctx.user_background or "unknown — ask if it matters",
            topic=topic,
            skill=skill or "(no specific reference loaded)",
        )
        ctx.add_exchange("user", user_input)
        return system

    def respond(self, ctx: SharedContext, user_input: str) -> str:
        system = self._prepare(ctx, user_input)
        # Send recent history so the tutor has continuity.
        reply = call_claude(system, ctx.session_history[-12:])
        ctx.add_exchange("assistant", reply)
        return reply

    def respond_stream(self, ctx: SharedContext, user_input: str):
        """Yield reply text deltas; record the full assistant turn at the end."""
        system = self._prepare(ctx, user_input)
        chunks = []
        for piece in stream_claude(system, ctx.session_history[-12:]):
            chunks.append(piece)
            yield piece
        ctx.add_exchange("assistant", "".join(chunks))
