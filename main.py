"""CLI entry point — wires everything into a loop.

  python main.py

Persists session state to PostgreSQL on exit (best-effort). Special commands:
  /help            show commands
  /domain pe|ne    switch domain
  /resume          run the resume / ATS assistant
  /progress        show your score history
  exit | quit      leave (saves session)
"""
import sys

import config
from context.shared_context import SharedContext
from agents.orchestrator import Orchestrator

USER_ID = "local-user"  # Phase 1 is single-user; Phase 3 adds real auth.

HELP = """
Commands:
  /help            this message
  /domain pe       switch to Production Engineering
  /domain ne       switch to Network Engineering
  /resume          resume / ATS assistant (analyze, tailor, cover letter)
  /progress        your score history and weak areas
  exit | quit      leave

Or just talk:
  "explain BGP path selection"        -> Tutor
  "start a mock"                      -> Interviewer (say 'done' to be scored)
  "start a mock with hints"           -> Interviewer with hints on
"""


# ------------------------------------------------------------ persistence
def load_context() -> SharedContext:
    try:
        from db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "SELECT context FROM sessions WHERE user_id = %s "
                "ORDER BY updated_at DESC LIMIT 1", (USER_ID,))
            row = cur.fetchone()
            if row:
                return SharedContext.from_json(row["context"])
    except Exception as e:
        print(f"  [warn] could not load prior session ({e}). Starting fresh.")
    return SharedContext(user_id=USER_ID)


def save_context(ctx: SharedContext) -> None:
    try:
        from db.connection import get_cursor
        from db.models import ensure_user
        ensure_user(ctx.user_id)
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO sessions (user_id, context) VALUES (%s, %s)",
                (USER_ID, ctx.to_json()))
        print("  Session saved.")
    except Exception as e:
        print(f"  [warn] could not save session: {e}")


# ------------------------------------------------------------ resume flow
def _read_block(prompt: str) -> str:
    """Read a multi-line block until a line containing only 'END'."""
    print(prompt + " (end with a line containing only END):")
    lines = []
    for line in sys.stdin:
        if line.strip() == "END":
            break
        lines.append(line.rstrip("\n"))
    return "\n".join(lines).strip()


def resume_flow(orch: Orchestrator, ctx: SharedContext) -> None:
    from agents.resume_agent import parse_resume_file
    print("\n— Resume / ATS Assistant —")
    src = input("Resume from (f)ile path or (p)aste? [f/p]: ").strip().lower()
    if src == "f":
        path = input("Path to resume (.pdf/.docx/.txt): ").strip()
        try:
            resume_text = parse_resume_file(path)
        except Exception as e:
            print(f"  Could not read file: {e}")
            return
    else:
        resume_text = _read_block("Paste your resume")
    ctx.base_resume_text = resume_text

    jd_text = _read_block("Paste the job description")
    if not resume_text or not jd_text:
        print("  Need both a resume and a job description.")
        return

    mode = input("Mode — (a)nalyze / (t)ailor / (c)over letter: ").strip().lower()
    mode_map = {"a": "analyze", "t": "tailor", "c": "cover_letter"}
    mode = mode_map.get(mode, "analyze")

    tone = None
    if mode == "cover_letter":
        tone = input("Tone (enter for default): ").strip() or None

    print("\n  Working...\n")
    result = orch.run_resume(ctx, mode, resume_text, jd_text, tone)

    if mode == "analyze":
        _print_ats_report(result)
    else:
        print(result)


def _print_ats_report(r: dict) -> None:
    if "error" in r:
        print(f"  Analysis problem: {r['error']}")
        return
    print(f"  ATS match score: {r.get('ats_score')}%\n")
    print("  Hard requirements:")
    for req in r.get("hard_requirements", []):
        mark = {"met": "[x]", "weak": "[~]", "missing": "[ ]"}.get(req.get("status"), "[?]")
        print(f"    {mark} {req.get('requirement')} ({req.get('status')})")
    if r.get("keywords_missing"):
        print(f"\n  Keywords to add: {', '.join(r['keywords_missing'])}")
    if r.get("preferred_quals_missing"):
        print(f"  Preferred quals missing: {', '.join(r['preferred_quals_missing'])}")
    print(f"\n  Verdict: {r.get('verdict')}")


# ------------------------------------------------------------ main loop
def main() -> None:
    problems = config.validate()
    if problems:
        print("Configuration issues:")
        for p in problems:
            print(f"  - {p}")
        print("Fix these (or some features will fail) — continuing anyway.\n")

    try:
        from db.models import init_db, ensure_user
        init_db()
    except Exception as e:
        print(f"  [warn] DB not initialised ({e}). Scores/sessions won't persist.\n")

    ctx = load_context()
    # Create the parent users row now so mid-session scores can persist.
    try:
        ensure_user(ctx.user_id)
    except Exception as e:
        print(f"  [warn] could not ensure user row: {e}")
    orch = Orchestrator()

    print("=" * 60)
    print("  Interview Mentor — multi-domain prep (PE + NE) + Resume/ATS")
    print(f"  Domain: {config.DOMAINS.get(ctx.current_domain)}  |  type /help")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue

        low = user_input.lower()
        if low in {"exit", "quit"}:
            break
        if low == "/help":
            print(HELP); continue
        if low.startswith("/domain"):
            parts = low.split()
            if len(parts) == 2 and parts[1] in config.DOMAINS:
                ctx.current_domain = parts[1]
                ctx.current_topic = None
                print(f"  Domain set to {config.DOMAINS[parts[1]]}.")
            else:
                print("  Usage: /domain pe   or   /domain ne")
            continue
        if low == "/resume":
            resume_flow(orch, ctx); continue
        if low == "/progress":
            print(orch.route(ctx, "progress")); continue

        try:
            print("\n" + orch.route(ctx, user_input))
        except Exception as e:
            print(f"  [error] {e}")

    save_context(ctx)
    print("Good luck with your prep. ")


if __name__ == "__main__":
    main()
