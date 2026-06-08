# Interview Mentor — Multi-Agent Prep Platform

A multi-agent AI platform for **Production Engineering (PE/SRE)** and
**Network Engineering (NE)** interview prep, plus a **Resume / ATS** assistant.
Agents share one `SharedContext` so the system behaves like a coach, not five
isolated bots.

> Adapted from the original PE-only build plan. Added: the Network Engineering
> domain, and a Resume/ATS assistant (analyze · tailor · cover letter).

## Agents
| Agent | What it does |
|---|---|
| Orchestrator | Routes every message; maintains domain + topic in SharedContext |
| Tutor | Explains concepts at your level using markdown skill files |
| Interviewer | Conducts mocks turn-by-turn, scores against a per-topic rubric |
| Resume/ATS | Analyzes resume vs JD, tailors the resume, writes cover letters |
| Resource (Phase 2) | Scheduled heartbeat that keeps the question bank fresh |
| Progress Tracker (Phase 4) | Per-domain weak-area tracking + prep plans |

## Domains & topics
- **PE:** coding · linux · troubleshooting · system_design
- **NE:** networking_fundamentals · routing · network_troubleshooting · network_design · network_security

## Prerequisites
- Python 3.11+
- PostgreSQL 14+ (running locally)
- An Anthropic API key

PostgreSQL is **not** currently installed on this machine. Install it first:
```bash
brew install postgresql@16
brew services start postgresql@16
createdb interview_prep
```

## Setup
```bash
cd interview_mentor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit .env with your key + DATABASE_URL
python main.py
```

## Using it
```
> /domain ne
> explain BGP path selection            # Tutor
> start a mock                          # Interviewer (say 'done' to be scored)
> /progress                             # score history
> /resume                               # resume / ATS assistant
```

## Resume / ATS assistant
`/resume` walks you through:
1. Provide your resume (file path to `.pdf`/`.docx`/`.txt`, or paste).
2. Paste the job description.
3. Pick a mode:
   - **analyze** — ATS match score + keyword gap report
   - **tailor** — full rewrite weaving in missing keywords (never fabricates)
   - **cover letter** — role-specific letter in your chosen tone

Every analysis/tailor/letter is saved to the `applications` table so you can
track what you sent where.

## Build phases
- **Phase 1 (this):** CLI — agents + Postgres + hardcoded question bank + resume assistant
- **Phase 2:** ChromaDB semantic question bank + Resource Agent heartbeat
- **Phase 3:** FastAPI + Streamlit UI (incl. a Resume Lab screen) + auth + Railway deploy
- **Phase 4:** Progress Tracker intelligence + proactive orchestrator + targeted drilling

## Notes
- Model: `claude-sonnet-4-6` (configurable via `MODEL_NAME`).
- Scores and sessions persist to PostgreSQL; resume outputs persist to `applications`.
