# Interview Mentor

A local web app for software-engineering interview prep: **Production Engineering / SRE**
(coding, Linux, troubleshooting, system design) and **Network Engineering** (fundamentals,
routing, troubleshooting, design, security). Two agents share one picture of you:

- **Tutor** — topic-aware coaching that remembers your profile, your mock scores, and your
  earlier sessions on the same topic.
- **Interviewer** — one question at a time from a curated bank, probing follow-ups, then a
  rubric score per dimension with a top fix and a model answer. Mocks are resumable.

Everything persists to PostgreSQL. The app runs as a macOS launchd agent, so it is always at
**http://127.0.0.1:8765** — no terminal, no scripts, just open the URL (or the Dock launcher).

## Requirements
- macOS, Python 3.11+
- PostgreSQL (Homebrew: `brew install postgresql@18 && brew services start postgresql@18`)
- An Anthropic API key

## First-time setup
```bash
cd interview_mentor
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
createdb interview_prep                       # once
cp .env.example .env                          # then put your ANTHROPIC_API_KEY in .env
scripts/install_launch_agent.sh               # starts at login, opens the browser
```
The install script also creates `~/Applications/Interview Mentor.app`, a one-click launcher
you can drag to the Dock. Logs go to `~/Library/Logs/interview-mentor.log`.

To run in the foreground instead (development, auto-reload): `scripts/serve.sh`.
To remove the background service: `scripts/uninstall_launch_agent.sh`.

## Using it
1. **Settings** — fill in your experience, target roles, interview date, and pick a model.
   The agents read this on every turn.
2. **Learn** — pick a topic, start a session, ask anything. Sessions are saved and listed;
   reopen one to continue.
3. **Mock interview** — pick topic and difficulty, answer as you would out loud, then
   *Finish & score*. You get per-dimension scores, a top fix, and what a strong answer covers.
   Refreshing or closing the tab does not lose a mock.
4. **Dashboard** — per-topic averages and trend, your weakest rubric dimensions, recent
   mocks and sessions, days to interview.
5. **Question bank** — browse every question, see which you have been scored on.

Switch between PE and NE with the toggle at the top of the sidebar.

## Layout
```
app/                FastAPI app: routes/pages.py (HTML), routes/api.py (streaming + actions),
                    templates/, static/ (plain CSS + one JS file, no build step)
agents/             base.py (Claude client, caching, streaming), tutor.py, interviewer.py,
                    resume_agent.py (importable; no UI page yet)
context/learner.py  LearnerContext — the per-request snapshot every agent reads
db/                 connection pool, schema (idempotent), repo.py (all queries)
question_bank/      questions/ (the bank, one markdown file each), store.py (parser/writer),
                    generator.py (Claude generation + enrichment), review.py (queue → file),
                    scraper + pipeline (optional)
skills/             markdown reference files prepended to prompts — edit to change what
                    the tutor treats as ground truth
scripts/            serve.sh, install/uninstall launch agent
tests/              pytest: offline unit tests + web tests against local Postgres
```

## Models and cost
Default model is `claude-opus-5`; `claude-sonnet-5` is selectable in Settings. Skill files
and personas are sent as a cached system prefix, so repeated turns on one topic re-bill that
part at the cached rate. Conversational turns use medium effort; scoring uses high effort.

## Tests
```bash
.venv/bin/python -m pytest -q
```
Web tests use a separate `pytest-user` learner id and clean up after themselves. They skip
if Postgres is unreachable. No test calls Claude.

## The question bank
Every question is a markdown file under `question_bank/questions/<domain>/<topic>/<id>.md` with
YAML frontmatter (id, difficulty, tags, companies, source, created) and fixed sections:
**Prompt**, **What interviewers look for**, **Strong answer covers**, **Follow-ups**, and an
optional **Sample answer**. The format and authoring rules are in
[question_bank/README.md](question_bank/README.md). The files are the source of truth; the
database holds only the review queue and your mock history.

The interviewer uses the follow-ups as probes, scoring reports which coverage points you hit,
and the sample answer is what you see after a mock.

### Growing it
1. **Question bank → Generate with Claude.** Pick a topic and a count. The generator reads the
   topic's skill file, the authoring rules, and every existing prompt so it does not repeat
   them, and writes fully structured candidates into the **review queue**.
2. **Review queue.** Edit any field, then *Save & approve* — that writes the markdown file with
   the next id for the topic (`ne-routing-007`) and it is live in mocks immediately. *Back to
   queue* removes the file again.
3. **Edit existing questions** from the bank page (each has an edit link) or in any editor.
   Questions added in the last two weeks are flagged new.
4. **Skill files page.** The nine reference files feed the tutor, the interviewer and the
   generator. Keep them opinionated: what the interview tests, frameworks, reference facts,
   common mistakes, practice prompts.
5. **Scraper (optional).** `python -m question_bank.pipeline --sources hackernews github`
   pulls public-source candidates into the same review queue.

## Not in this version
- Resume / ATS lab UI (the agent in `agents/resume_agent.py` still works from Python)
- Multi-user accounts / cloud deployment
- In-browser code editor for coding mocks (answers are typed or pasted as text)
