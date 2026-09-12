"""Tutor agent — explains concepts at the learner's level, with memory.

Stateless: the caller passes a LearnerContext (profile, performance, prior
sessions) and the current conversation's message history. The system prompt
carries the skill markdown for the topic as ground truth.
"""
from __future__ import annotations

import config
from agents.base import load_skill, stream_claude
from context.learner import LearnerContext

HISTORY_WINDOW = 30  # messages sent per turn; older turns are dropped

SYSTEM = """You are an expert interview tutor for {domain}, coaching one learner
one-on-one over many sessions. Today's topic: {topic}.

## The learner
{profile}
{focus}
## Their mock-interview record in this domain
{performance}

## Earlier tutoring sessions on this topic
{prior_sessions}

## How to teach
- Teach the way a senior engineer mentors: concrete, precise, no filler. Use small
  examples, commands, or diagrams in text where they help.
- Adapt depth to the learner's level and to the interview timeline above. Close to the
  interview, prioritise what is most likely to be asked.
- When a job-specific focus block is present above, teach to that job: use its vocabulary
  and stay at the level it names. Do not broaden into the wider topic unless they ask.
- When their record shows weak rubric dimensions, connect explanations back to those
  gaps without being preachy about it.
- After explaining something non-trivial, check understanding with one short question,
  then wait. Do not stack several questions.
- If they ask for a practice question, give one and coach them through it; if they
  want a scored mock, tell them to use the Mock page.
- Use Markdown. Code in fenced blocks with a language tag.

## Reference material ({topic}) — treat as ground truth
{skill}
"""


class Tutor:
    def system_prompt(self, ctx: LearnerContext) -> str:
        skill = load_skill(ctx.topic) or "(no reference file for this topic)"
        focus = ctx.focus_text()
        return SYSTEM.format(
            domain=ctx.domain_label,
            topic=ctx.topic_label,
            profile=ctx.profile_text(),
            focus=f"\n{focus}\n" if focus else "",
            performance=ctx.performance_text(),
            prior_sessions=ctx.prior_sessions_text(),
            skill=skill,
        )

    def stream_reply(self, ctx: LearnerContext, history: list[dict], user_input: str):
        """Yield reply text deltas. `history` excludes the new user message."""
        messages = [{"role": m["role"], "content": m["content"]}
                    for m in history[-HISTORY_WINDOW:]]
        messages.append({"role": "user", "content": user_input})
        yield from stream_claude(self.system_prompt(ctx), messages,
                                 max_tokens=config.MAX_TOKENS_CHAT,
                                 effort=config.EFFORT_CHAT, model=ctx.model)

    @staticmethod
    def title_from(first_message: str) -> str:
        """A conversation title from the learner's first message. No API call."""
        text = " ".join(first_message.split())
        return (text[:57] + "…") if len(text) > 60 else text or "New session"
