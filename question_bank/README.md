# Question bank — format and authoring rules

One markdown file per question under `questions/<domain>/<topic>/<id>.md`. The files are the
source of truth: they are what mocks draw from, what the Question bank page shows, and what
`git diff` tracks. The database holds only the review queue and your mock history.

## File format
```markdown
---
id: ne-routing-003          # <domain>-<topic>-<nnn>, continuous numbering, never reused
domain: ne
topic: routing
difficulty: hard            # easy | medium | hard
tags: [bgp, convergence]
companies: []               # optional: where it is known to be asked
source: generated           # seed | generated | scraped | manual
created: 2026-09-11
---
# Prompt
The question exactly as an interviewer would say it. Self-contained.

## What interviewers look for
- The signals a strong candidate shows (used by the interviewer to probe, and by scoring)

## Strong answer covers
1. Numbered coverage points. Scoring reports which of these the candidate hit.
2. Be concrete: commands, numbers, protocol behaviour, trade-offs.

## Follow-ups
- Questions the interviewer asks when the candidate is doing well (or to test depth)

## Sample answer
Optional. Spoken-prose model answer shown after the mock.
```

## Authoring rules (humans and the generator)
- **Self-contained.** Everything needed to answer is in the prompt. No "as discussed above".
- **Realistic production framing.** Incidents, designs under constraints, "what do you check
  first", reading output. Not trivia.
- **No company names inside the prompt.** Tag them in `companies:` instead so the same question
  can be reused generically.
- **Difficulty by time-to-strong-answer:** easy 3–5 min, medium 8–12 min, hard 15–20 min with
  several dimensions most candidates miss.
- **Coverage points are specific and checkable.** "Mentions hold timer 180 s default and BFD"
  beats "understands timers".
- **Follow-ups escalate.** Each should test something the coverage list does not already cover.
- **Never leak the answer in the prompt.**

## Workflow
Generate candidates on the Question bank page → edit and approve in the Review queue → the
file is written here. Edit any existing question from its page in the app or in an editor.
