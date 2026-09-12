"""Print the exact prompt an agent would send, without calling Claude.

Prompt building is pure — the agents turn a LearnerContext into a string with no
side effects — so this costs nothing and is the fastest way to see the effect of
editing a prompt, a skill file, or a focus area. For what was *actually* sent on a
real run, set IM_DEBUG_PROMPTS=1 instead and read prompts.log.

    .venv/bin/python scripts/show_prompt.py plan --jd jd.txt
    .venv/bin/python scripts/show_prompt.py plan --jd jd.txt --resume other.txt --domain pe
    .venv/bin/python scripts/show_prompt.py tutor --conversation 42
    .venv/bin/python scripts/show_prompt.py tutor --topic linux --focus 7
    .venv/bin/python scripts/show_prompt.py mock --mock 12
    .venv/bin/python scripts/show_prompt.py plans            # list plans and focus area ids
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config                                          # noqa: E402
from db import repo                                    # noqa: E402

USER = config.USER_ID


def _rule(label: str) -> None:
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")


def _resume_text(path: str | None) -> str:
    if path:
        from agents.resume_agent import parse_resume_file
        return parse_resume_file(path)
    resume = repo.get_base_resume(USER)
    if not resume:
        sys.exit("No resume on file. Add one in Settings, or pass --resume PATH.")
    return resume["content_text"]


def show_plan(args) -> None:
    from agents.planner import Planner, bank_text, performance_text, plan_messages
    jd = Path(args.jd).read_text(encoding="utf-8")
    domain = args.domain if args.domain in config.DOMAINS else None
    _rule("PLANNER · SYSTEM")
    print(Planner().system_prompt(domain, performance_text(USER), bank_text()))
    _rule("PLANNER · USER")
    for message in plan_messages(_resume_text(args.resume), jd):
        print(message["content"])


def _context(domain: str, topic: str, focus_id: int | None, exclude: int | None = None):
    from context.learner import build_context
    focus = None
    if focus_id:
        focus = repo.get_focus(focus_id, USER)
        if not focus:
            sys.exit(f"No focus area {focus_id} for user {USER}. Try: show_prompt.py plans")
        domain, topic = focus["domain"], focus["topic"]
    return build_context(USER, domain, topic, exclude_conversation=exclude, focus=focus)


def show_tutor(args) -> None:
    from agents.tutor import Tutor
    if args.conversation:
        conv = repo.get_conversation(args.conversation, USER)
        if not conv:
            sys.exit(f"No conversation {args.conversation} for user {USER}.")
        ctx = _context(conv["domain"], conv["topic"], conv.get("focus_id"),
                       exclude=args.conversation)
        print(f"# conversation {conv['id']}: {conv['title']!r} "
              f"({len(repo.list_messages(conv['id']))} messages so far)")
    else:
        domain = config.domain_for_topic(args.topic)
        if not domain and not args.focus:
            sys.exit(f"Unknown topic {args.topic!r}. One of: "
                     + ", ".join(t for ts in config.TOPICS.values() for t in ts))
        ctx = _context(domain or "pe", args.topic, args.focus)
    _rule("TUTOR · SYSTEM")
    print(Tutor().system_prompt(ctx))


def show_mock(args) -> None:
    from agents.interviewer import Interviewer
    mock = repo.get_mock(args.mock, USER)
    if not mock:
        sys.exit(f"No mock {args.mock} for user {USER}.")
    ctx = _context(mock["domain"], mock["topic"], mock.get("focus_id"))
    _rule(f"INTERVIEWER · SYSTEM (mock {mock['id']}, question {mock['question_id']})")
    print(Interviewer().conduct_prompt(ctx, mock))


def show_plans(_args) -> None:
    targets = repo.list_targets(USER, status=None)
    if not targets:
        print("No job plans yet.")
        return
    for target in targets:
        print(f"\nplan {target['id']}: {target['role'] or '?'} at "
              f"{target['company'] or '?'} [{target['status']}]")
        for area in repo.list_focus_areas(target["id"]):
            print(f"  focus {area['id']:>4}  {area['level']:<7} {area['topic']:<24} "
                  f"{area['title']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)

    plan = subs.add_parser("plan", help="the planner prompt for a job description")
    plan.add_argument("--jd", required=True, help="path to a file holding the JD text")
    plan.add_argument("--resume", help="path to a resume file (default: the one on file)")
    plan.add_argument("--domain", default="auto", help="pe | ne | auto (default: auto)")
    plan.set_defaults(func=show_plan)

    tutor = subs.add_parser("tutor", help="the tutor prompt")
    tutor.add_argument("--conversation", type=int, help="an existing conversation id")
    tutor.add_argument("--topic", default="linux", help="topic id, when there is no conversation")
    tutor.add_argument("--focus", type=int, help="a focus area id, to include the job context")
    tutor.set_defaults(func=show_tutor)

    mock = subs.add_parser("mock", help="the interviewer prompt for a mock")
    mock.add_argument("--mock", type=int, required=True, help="a mock id")
    mock.set_defaults(func=show_mock)

    subs.add_parser("plans", help="list job plans and focus area ids").set_defaults(
        func=show_plans)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
