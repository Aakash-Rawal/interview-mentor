# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-user, local web app for PE/SRE and Network Engineering interview prep: a Tutor
(topic chat with memory), an Interviewer (scored mock interviews), and a Planner (resume + job
description -> a per-job study checklist), all backed by Claude.
FastAPI + Jinja2 + one vanilla JS file; PostgreSQL for state; no Node, no build step.
It normally runs as a macOS launchd agent at http://127.0.0.1:8765.

## Commands

```bash
.venv/bin/python -m pytest -q                      # full suite (~1 s)
.venv/bin/python -m pytest -q tests/test_store.py  # one file
.venv/bin/python -m pytest -q -k review_queue      # one test by name
scripts/serve.sh                                   # dev server with --reload (port 8765)
launchctl kickstart -k "gui/$(id -u)/com.interviewmentor.server"   # restart the installed service after code changes
tail -f ~/Library/Logs/interview-mentor.log        # service log
scripts/install_launch_agent.sh                    # (re)install the service; uninstall_launch_agent.sh removes it
python -m question_bank.pipeline --sources hackernews github        # optional scraper -> review queue
.venv/bin/python scripts/show_prompt.py plans                      # plan + focus area ids
.venv/bin/python scripts/show_prompt.py tutor --conversation 42    # the prompt an agent would send
IM_DEBUG_PROMPTS=1 scripts/serve.sh                                # log every prompt to prompts.log
```

Tests need local Postgres (`DATABASE_URL` in `.env`); web tests skip if it is unreachable.
`tests/conftest.py` forces `INTERVIEW_MENTOR_USER_ID=pytest-user` and a dummy API key, and
its `purge_user()` helper is every module fixture's teardown (FK-safe, so the suite does not
depend on file order). No test calls Claude: agents are monkeypatched
(`api.tutor.stream_reply`, `api.interviewer.stream_turn/score`, `api.planner.build_plan`,
`generator.call_claude`).
Tests that touch the question bank monkeypatch `store.QUESTIONS_DIR` to `tmp_path` and call
`store.invalidate()`.

The installed launchd service does **not** auto-reload: restart it (command above) after
changing Python or templates. Question files and skill files are re-read on change without a
restart.

## Architecture

**Request flow.** `app/routes/pages.py` renders HTML; `app/routes/api.py` handles form posts
and streaming. Chat and mock turns are `StreamingResponse` of plain text read by
`app/static/chat.js` via `fetch` + `ReadableStream`; a mid-stream failure is appended after
`api.ERROR_MARKER` (`\n\x1e ERROR: `) and the JS splits on it. The `on_complete` callback in
`api._stream` is what persists the assistant turn, so a stream that errors persists nothing.

**Agents are stateless.** `context/learner.py::build_context()` assembles a fresh
`LearnerContext` per request from the DB (profile, per-topic performance, prior sessions on
the topic, and the focus area when studying a job plan — its role and interview date then win
over the profile's, and `focus_text()` becomes a prompt block in both agents). `agents/tutor.py` and `agents/interviewer.py` only build prompts and call
`agents/base.py`; all conversation and mock state lives in Postgres via `db/repo.py`.
A mock row stores a JSON snapshot of its question at start time, so editing a question file
does not change an in-progress or finished mock.

**Claude calls** go through `agents/base.py` only: cache-controlled system prompt, adaptive
thinking, `output_config.effort` (`EFFORT_CHAT` for turns, `EFFORT_SCORE` for scoring and
generation). `call_claude` streams under the hood and raises `ClaudeError` on refusal or
`max_tokens` truncation; `stream_claude` yields deltas. Model is per-user (Settings) with
`config.DEFAULT_MODEL` fallback; only ids in `config.MODELS` are allowed.

**Job plans.** `agents/planner.py` takes the stored resume (`resumes`, `is_base`) plus a pasted
JD and returns focus areas; `job_targets` is one row per job being chased and `focus_areas` its
checklist. `conversations.focus_id` / `mocks.focus_id` tag study done against a focus area, so
plan progress is a query rather than bookkeeping, and deleting a plan leaves the chats and mocks
behind. A focus area's `topic` is only where its practice material comes from (skill file,
rubric, question pool) — the `title` is the subject, and a loose topic fit is expected. `level`
carries the distinction that matters: `tool` means the JD hires for operating something
(Kubernetes, Terraform), so the tutor and interviewer stay at usage level; `concept` means the
idea itself, so they go for depth. `normalise_plan()` closes the topic set — an unrecognised
topic moves to the plan's `unmapped` list instead of being dropped or force-fit — and topics
from the other domain are kept, with a focus area's real domain derived from its topic
(`repo._focus_row`), so a PE plan can hold a routing focus area. The plan is a fixed checklist:
nothing re-prioritises it as scores change. Growing the bank for a thin focus area is not wired
in yet; use the Question bank page.

**Seeing what an agent sent.** Two ways, and they answer different questions.
`IM_DEBUG_PROMPTS=1` makes `agents/base.py::_request` append every system prompt and message
list to `config.DEBUG_PROMPT_LOG` (`prompts.log`, gitignored) just before the call — one hook,
so it covers tutor, interviewer, planner and generator, and it logs even when the call then
fails. `scripts/show_prompt.py` instead *previews* a prompt with no API call, which works
because prompt building is pure; it shares `planner.plan_messages()` with the real call so a
preview cannot drift from what is sent. Restart the service after either (Python changed).

**Skill files** (`skills/<domain>/*.md`) are prepended to tutor, interviewer, and generator
prompts as ground truth and are editable in the app. `load_skill` is `lru_cache`d; the skill
save endpoint calls `load_skill.cache_clear()`.

**Question bank** is markdown files under `question_bank/questions/<domain>/<topic>/<id>.md`
parsed by `question_bank/store.py` (YAML frontmatter + `# Prompt`, `## What interviewers look
for`, `## Strong answer covers`, `## Follow-ups`, `## Sample answer`). The files are the
source of truth; `question_bank/questions.py` is the query layer over `store.load_all()`.
Format and authoring rules: `question_bank/README.md`. Do not reintroduce a Python list of
questions. Ids are `<domain>-<topic>-<nnn>` (continuous per topic via `store.next_id`); the
original seeded questions keep their short ids (`pe-cod-01`).

**Growth loop.** `question_bank/generator.py` asks Claude for structured candidates (and
`enrich()` fills structure for prompt-only questions) → rows in `scraped_questions` with
`approved=false` are the review queue → `question_bank/review.py::promote()` writes the
markdown file and marks the row with `promoted_id`; `demote()` reverses it. Approved rows are
history only and are never merged into the bank. Keep generation/enrichment batches small
(≤ 12 items): the output includes sample answers and thinking counts against `max_tokens`.

**Schema** lives in `db/models.py` as idempotent statements (`CREATE TABLE IF NOT EXISTS`,
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`); `init_db()` runs on every boot with retries, so
add columns there rather than migrating by hand. Legacy `sessions`, `messages`, `scores`
tables may exist in a local DB and are unused.

**Domains and topics** are defined once in `config.py` (`DOMAINS`, `TOPICS`, `TOPIC_LABELS`,
`SKILL_FILES`); rubric dimensions per topic are in `agents/interviewer.py::RUBRICS`. Adding a
topic means touching all of these plus a skill file and at least one question file, and
`tests/test_core.py` enforces that.

**Not wired into the UI:** `agents/resume_agent.py`'s analyze / tailor / cover_letter modes
(they work from Python; only its `parse_resume_file` is used, by the resume upload) and the
scraper pipeline (CLI only, feeds the same review queue).
