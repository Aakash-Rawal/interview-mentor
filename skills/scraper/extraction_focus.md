# Scraper Extraction Focus

This file is injected into the question-extraction prompt every time the scraper
pipeline runs. Edit it to change what kinds of questions get prioritised.
The JSON output format and domain/topic rules are fixed by the code — only the
guidance below is yours to change.

---

## Goal

Extract high-quality technical interview questions that reflect the real interview
bar at top-tier tech companies and AI startups: Google, Meta, Netflix, Nvidia,
Cloudflare, Stripe, OpenAI, Anthropic, Apple, Amazon, and similar organisations.

This app is used to prepare for Production Engineering, SRE, and Network Engineering
roles across the industry — not any single company.

---

## Prioritise questions that

- Test **depth of understanding**, not just recall. "Explain what happens end-to-end
  when X" is better than "What does X stand for?"
- Reflect **real oncall / production scenarios** that an engineer at a large company
  would actually face.
- Require the candidate to **reason under ambiguity** — incomplete information,
  trade-offs, failure modes.
- Are **specific and self-contained** — a candidate should be able to answer it
  without needing extra context beyond what's in the prompt.
- Cover **modern infrastructure**: cloud-native systems, containerisation, large-scale
  distributed systems, observability, reliability engineering, AI/ML infrastructure
  where relevant to PE/NE roles.

---

## Difficulty calibration

- **easy** — a competent mid-level engineer answers confidently in 2-3 minutes.
- **medium** — requires structured thinking; a strong answer takes 5-10 minutes.
- **hard** — open-ended, system-scale, or requires expert-level nuance; a complete
  answer takes 10-15 minutes and most candidates miss at least one dimension.

Aim for a mix across all three levels. Do not assign "hard" just because a topic
sounds advanced — rate by how long a thorough answer takes and how many candidates
would get it fully right.

---

## Source-specific notes

**GitHub repos** — content is often a structured list (e.g. "Q: ... A: ...") or a
numbered set of interview questions with explanations. Extract each distinct question
as its own entry. The expected_answer_notes can be drawn from the answer/explanation
already present in the file. These tend to be high-quality — score generously if the
question is specific and the answer is substantive.

**Hacker News threads** — content is conversational. Look for questions embedded in
comments like "they asked me...", "one question that stumped me was...", or
"a good way to test X is to ask...". The signal is sparser than GitHub but the
questions reflect what interviewers are actually asking right now.

**Reddit / Stack Exchange** — already handled well. Same guidance as HN for Reddit;
SE questions themselves often map directly to interview prompts.

---

## Deprioritise (quality_score ≤ 4)

- Trivia or definitions ("What is BGP?", "What does SRE stand for?")
- Questions that are too broad to score objectively ("Tell me about networking")
- Questions specific to a niche proprietary tool most engineers won't have used
- Behavioural / HR questions (this bank is technical only)
- Duplicate signals of an already-common question
- Setup/installation instructions found in GitHub READMEs (not interview questions)
