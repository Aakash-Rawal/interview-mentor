"""Offline tests: config, question bank, prompts, context. No Claude, no Postgres."""
import random
from datetime import date, timedelta

import config
from agents.interviewer import DEFAULT_RUBRIC, RUBRICS, Interviewer, parse_json_object
from agents.tutor import Tutor
from context.learner import LearnerContext
from question_bank.questions import all_questions, get_questions


def test_every_topic_has_skill_rubric_and_questions():
    for domain, topics in config.TOPICS.items():
        for t in topics:
            assert t in config.SKILL_FILES, t
            assert (config.SKILLS_DIR / config.SKILL_FILES[t]).exists(), t
            assert t in RUBRICS, t
            assert get_questions(domain, t), f"no questions for {domain}/{t}"


def test_question_bank_is_well_formed():
    from question_bank import store
    assert not store.load_errors()
    ids = [q["id"] for q in all_questions()]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    assert len(ids) >= 60
    for q in all_questions():
        assert q["domain"] in config.DOMAINS
        assert q["topic"] in config.TOPICS[q["domain"]]
        assert q["difficulty"] in config.DIFFICULTIES
        assert q["prompt"].strip() and q["covers"] and q["expected_answer_notes"].strip()


def test_pick_question_respects_exclusions_and_difficulty():
    rng = random.Random(1)
    pool = get_questions("pe", "coding")
    seen = {q["id"] for q in pool[:-1]}
    q = Interviewer.pick_question("pe", "coding", "any", seen, rng)
    assert q["id"] == pool[-1]["id"]
    q = Interviewer.pick_question("ne", "routing", "hard", set(), rng)
    assert q["difficulty"] == "hard"
    # everything covered -> still returns something rather than None
    q = Interviewer.pick_question("pe", "linux", "any", {x["id"] for x in pool + get_questions("pe", "linux")}, rng)
    assert q is not None


def _ctx(**kw):
    base = dict(user_id="t", domain="ne", topic="routing", model="claude-opus-5")
    base.update(kw)
    return LearnerContext(**base)


def test_learner_context_prompt_fragments():
    ctx = _ctx(background={"experience": "3 years", "language": "python"},
               target_role="Network Eng L5", interview_date=date.today() + timedelta(days=9),
               performance={"routing": {"count": 2, "avg": 6.5, "last": 7.0, "prev_avg": 6.0,
                                        "dimensions": {"failure_analysis": 4.0, "protocol_knowledge": 8.0},
                                        "top_fixes": ["Explain hold timers precisely."]}})
    p = ctx.profile_text()
    assert "3 years" in p and "python" in p and "in 9 days" in p and "Network Eng L5" in p
    perf = ctx.performance_text()
    assert "failure_analysis 4.0/10" in perf and "Explain hold timers" in perf
    assert ctx.days_to_interview() == 9
    assert _ctx().performance_text().startswith("No scored mocks")


def test_tutor_prompt_includes_skill_and_memory():
    ctx = _ctx(prior_sessions=[{"title": "BGP path selection", "created_at": date(2026, 9, 1)}])
    system = Tutor().system_prompt(ctx)
    assert "BGP" in system                      # skill file content
    assert "BGP path selection (Sep 01)" in system
    assert Tutor.title_from("  explain   BGP   ") == "explain BGP"
    assert len(Tutor.title_from("x" * 200)) == 58


def test_interviewer_messages_start_with_user_turn():
    transcript = [{"role": "assistant", "content": "Q?"}, {"role": "user", "content": "A."},
                  {"role": "assistant", "content": "Why?"}]
    msgs = Interviewer.api_messages(transcript, "Because.")
    assert msgs[0]["role"] == "user" and msgs[-1] == {"role": "user", "content": "Because."}
    roles = [m["role"] for m in msgs]
    assert all(a != b for a, b in zip(roles, roles[1:])), "roles must alternate"


def test_conduct_prompt_hint_rule_and_notes():
    ctx = _ctx()
    q = get_questions("ne", "routing")[0]
    mock = {"question": q, "difficulty": "hard", "hints": True, "topic": "routing"}
    s = Interviewer().conduct_prompt(ctx, mock)
    assert "Hints are ON" in s and q["covers"][0] in s
    mock["hints"] = False
    assert "Hints are OFF" in Interviewer().conduct_prompt(ctx, mock)


def test_debug_prompt_log_is_off_by_default_and_captures_every_call(tmp_path, monkeypatch):
    """IM_DEBUG_PROMPTS: one hook in _request covers every agent's calls."""
    import config
    from agents import base

    log = tmp_path / "prompts.log"
    monkeypatch.setattr(config, "DEBUG_PROMPT_LOG", log)

    monkeypatch.setattr(config, "DEBUG_PROMPTS", False)
    base._request("sys prompt", [{"role": "user", "content": "hi"}], 100, "medium", None)
    assert not log.exists()

    monkeypatch.setattr(config, "DEBUG_PROMPTS", True)
    request = base._request("SYSTEM TEXT", [{"role": "user", "content": "USER TEXT"}],
                            100, "high", "claude-opus-5")
    assert request["system"][0]["text"] == "SYSTEM TEXT"      # logging does not alter the call
    written = log.read_text()
    assert "SYSTEM TEXT" in written and "USER TEXT" in written
    assert "model=claude-opus-5" in written and "effort=high" in written

    base._request("SECOND CALL", [], 100, "medium", None)
    assert "SYSTEM TEXT" in log.read_text() and "SECOND CALL" in log.read_text()  # appends

    # An unwritable log warns, it never breaks the Claude call.
    monkeypatch.setattr(config, "DEBUG_PROMPT_LOG", tmp_path / "no" / "such" / "dir" / "p.log")
    assert base._request("still works", [], 100, "medium", None)["max_tokens"] == 100


def test_parse_json_object_tolerates_prose():
    assert parse_json_object('Sure:\n{"total": 7.5, "dimensions": {}}\nDone.')["total"] == 7.5
    assert "error" in parse_json_object("no json here")
    assert DEFAULT_RUBRIC
