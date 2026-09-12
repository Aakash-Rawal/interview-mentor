"""Planner agent — resume + job description -> a short study plan.

One Claude call per plan. Output is a set of focus areas, each assigned exactly
one topic from config.TOPICS so the rest of the app (skill file, rubric, question
pool) keeps working unchanged.

The topic is only the *practice material* for a focus area, not its subject. The
title is the subject. That distinction matters because job descriptions are mostly
written in tools: a JD asking for Kubernetes is hiring someone who can operate it,
not someone who can recite cgroup internals, so the focus area stays at the level
the JD hires for (`level="tool"`) and borrows whichever topic is the closest fit
for practice — a loose fit is fine and expected.

Stateless, like the other agents: build a prompt, call agents/base.py, return dicts.
Nothing is written to the database here; the route persists the result.
"""
from __future__ import annotations

import json

import config
from agents.base import call_claude
from db import repo

JD_CHARS = 12_000        # a JD longer than this is padding; trim it
RESUME_CHARS = 12_000

PLAN_SYSTEM = """You are an interview coach who has prepared hundreds of engineers for
{domains} interviews. You are given one candidate's resume and one job description.
Produce the short list of things this candidate should study for THIS job.

## Topics you may assign (closed list — never invent one)
{topics}

## Choosing the topic for a focus area
Every focus area gets exactly one topic from the list above. The topic decides only which
reference material, rubric, and practice questions we use. It is NOT the subject of the
focus area — the title is. A loose topic fit is acceptable; a wrong subject is not.

Tools are not concepts. When a JD names a tool or platform (Kubernetes, Terraform, Kafka,
Envoy, Prometheus, Ansible, a cloud provider), interviewers for that role test whether the
candidate can USE it well — the workflows, the flags and knobs that matter, the failure
modes an operator actually sees, the trade-offs in how it is applied. They rarely test how
it is implemented underneath. So:
- Write the focus area at the level the job hires for, set "level": "tool", and pick the
  closest-fitting topic for practice even if the fit is imperfect.
- "Kubernetes resource limits and pod evictions" is a correct focus area.
  "Linux cgroup internals" is a WRONG rewrite of it — do not convert a tool requirement
  into a theory requirement unless the JD genuinely asks for that depth (kernel work,
  protocol implementation, writing the control plane).
Use "level": "concept" only when the JD asks for the idea itself: BGP path selection,
consistent hashing, TCP congestion control, capacity estimation.

## How to choose WHAT to study
- Weight by how central it is to the JD, times how little evidence the resume shows for it.
  Something the JD leans on heavily and the resume never mentions is the top priority.
- Leave out anything the resume already demonstrates well — list those under "strengths"
  instead. Subtraction is the point: this is a checklist the candidate can finish.
- Ground every focus area in the actual documents. "why_jd" quotes or closely paraphrases
  what the JD asks for. "gap" says what the resume does or does not show. Never invent
  experience the resume does not contain, and never invent a requirement the JD does not state.
- Return between 3 and {max_areas} focus areas, fewer if the honest answer is fewer.
- "keywords": the JD's own vocabulary for this area (tool names, protocols, exact phrases),
  1-6 short lowercase terms. These are used to pick practice questions and to keep the
  tutor speaking in the JD's language.
- If the JD requires something no topic can host for practice, put it in "unmapped"
  instead of forcing it into a focus area.

## The candidate's mock-interview record so far
{performance}

## Practice questions currently in the bank, per topic
{bank}
Prefer topics with questions available when two are an equally good fit; if the best fit
is a thin topic, still use it and say so in "gap".

The list above spans both domains on purpose. Assign the topic that fits the focus area,
even when it belongs to the other domain — a production engineering job that leans on routing
gets a routing focus area.

## Output
Return ONLY valid JSON in exactly this shape, no prose around it:
{{
  "company": "<from the JD, or ''>",
  "role": "<the role title from the JD>",
  "domain": {domain_rule},
  "seniority": "<junior | mid | senior | staff | '' if unclear>",
  "summary": "<2-3 sentences: what this interview loop will actually test, and where this
               candidate stands against it>",
  "focus_areas": [
    {{
      "title": "<the subject to study, in the JD's terms, max 80 chars>",
      "topic": "<one topic id from the closed list>",
      "level": "tool" | "concept",
      "priority": <1 = study first>,
      "why_jd": "<what the JD asks for, quoted or closely paraphrased>",
      "gap": "<what the resume shows or fails to show for this>",
      "keywords": ["<jd vocabulary>", ...]
    }}
  ],
  "strengths": ["<what the resume already covers well enough to skip, with the evidence>"],
  "unmapped": ["<JD requirements no topic can host for practice>"]
}}"""


class Planner:
    def system_prompt(self, domain: str | None, performance: str, bank: str) -> str:
        # Every topic is offered whatever the job's primary domain is: a production
        # engineering role that leans on BGP should get a routing focus area, not lose it.
        topics = [(d, t) for d, ts in config.TOPICS.items() for t in ts]
        domain_rule = (f'"{domain}"' if domain else
                       '"' + '" | "'.join(config.DOMAINS) +
                       '" — whichever domain this job mostly belongs to')
        lines = [f"- {t}  ({config.topic_label(t)}, {config.DOMAINS[d]})" for d, t in topics]
        return PLAN_SYSTEM.format(
            domains=" and ".join(config.DOMAINS.values()),
            topics="\n".join(lines),
            domain_rule=domain_rule,
            max_areas=config.MAX_FOCUS_AREAS,
            performance=performance or "No scored mocks yet.",
            bank=bank,
        )

    def build_plan(self, resume_text: str, jd_text: str, *, domain: str | None = None,
                   performance: str = "", bank: str = "", model: str | None = None) -> dict:
        """Analyse resume + JD and return a validated plan dict. Raises ClaudeError."""
        if len(jd_text.strip()) < 80:
            raise ValueError("The job description is too short to analyse.")
        if len(resume_text.strip()) < 80:
            raise ValueError("Add your resume in Settings before creating a plan.")
        raw = call_claude(
            self.system_prompt(domain, performance, bank),
            plan_messages(resume_text, jd_text),
            max_tokens=config.MAX_TOKENS_LONG, effort=config.EFFORT_SCORE, model=model)
        return normalise_plan(parse_json_object(raw), domain)


def plan_messages(resume_text: str, jd_text: str) -> list[dict]:
    """The user turn for a plan. Shared with scripts/show_prompt.py so a preview
    cannot drift from what is actually sent."""
    return [{"role": "user", "content":
             f"=== RESUME ===\n{resume_text[:RESUME_CHARS]}\n\n"
             f"=== JOB DESCRIPTION ===\n{jd_text[:JD_CHARS]}\n\n"
             "Build the study plan now."}]


def bank_text() -> str:
    """Per-topic question counts, for the prompt."""
    from question_bank.questions import bank_counts
    counts = bank_counts()
    lines = []
    for d, topics in config.TOPICS.items():
        for t in topics:
            lines.append(f"- {t}: {counts.get(d, {}).get(t, 0)}")
    return "\n".join(lines)


def performance_text(user_id: str) -> str:
    """The learner's scored-mock record across both domains, for the prompt."""
    summary = repo.performance_summary(user_id)
    lines = []
    for domain, topics in summary.items():
        for topic, t in topics.items():
            lines.append(f"- {config.topic_label(topic)} ({domain}): {t['count']} mock(s), "
                         f"avg {t['avg']}/10, last {t['last']}/10")
    return "\n".join(lines)


# ------------------------------------------------------------------ validation
def normalise_plan(plan: dict, domain: str | None = None) -> dict:
    """Make planner output safe to store: a closed topic set, no gaps, capped length.

    A focus area whose topic is not a real topic is not dropped silently — it moves to
    `unmapped`, where the plan page shows it. That keeps a JD requirement visible
    instead of quietly disappearing or being force-fit into the wrong practice pool.

    `domain` is the plan's primary label only. Topics from the other domain are kept:
    a focus area's own domain is derived from its topic wherever it is used.
    """
    if "error" in plan:
        return plan
    unmapped = [str(u).strip() for u in _as_list(plan.get("unmapped")) if str(u).strip()]
    resolved = domain or _clean_domain(plan.get("domain")) or _infer_domain(plan)

    areas = []
    for raw in _as_list(plan.get("focus_areas")):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()[:120]
        topic = str(raw.get("topic") or "").strip().lower()
        if not title:
            continue
        if not config.domain_for_topic(topic):
            unmapped.append(f"{title} (no matching topic for '{topic or 'unspecified'}')")
            continue
        level = str(raw.get("level") or "").strip().lower()
        areas.append({
            "title": title,
            "topic": topic,
            "level": level if level in config.FOCUS_LEVELS else "concept",
            "priority": _as_int(raw.get("priority"), 5),
            "why_jd": str(raw.get("why_jd") or "").strip(),
            "gap": str(raw.get("gap") or "").strip(),
            "keywords": _keywords(raw.get("keywords")),
        })

    areas.sort(key=lambda a: a["priority"])
    dropped = areas[config.MAX_FOCUS_AREAS:]
    areas = areas[:config.MAX_FOCUS_AREAS]
    unmapped.extend(f"{a['title']} (over the {config.MAX_FOCUS_AREAS}-area plan limit)"
                    for a in dropped)
    for i, a in enumerate(areas, start=1):
        a["priority"] = i            # resequence: priorities are display order, not scores

    return {
        "company": str(plan.get("company") or "").strip()[:120],
        "role": str(plan.get("role") or "").strip()[:120],
        "domain": resolved,
        "seniority": str(plan.get("seniority") or "").strip()[:40],
        "summary": str(plan.get("summary") or "").strip(),
        "focus_areas": areas,
        "strengths": [str(s).strip() for s in _as_list(plan.get("strengths")) if str(s).strip()],
        "unmapped": unmapped,
    }


def parse_json_object(raw: str) -> dict:
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"error": "Could not parse the plan", "raw": raw}


def _clean_domain(value) -> str | None:
    d = str(value or "").strip().lower()
    return d if d in config.DOMAINS else None


def _infer_domain(plan: dict) -> str:
    """No usable domain in the output: take the one most of the topics belong to."""
    votes: dict[str, int] = {}
    for raw in _as_list(plan.get("focus_areas")):
        if isinstance(raw, dict):
            d = config.domain_for_topic(str(raw.get("topic") or "").strip().lower())
            if d:
                votes[d] = votes.get(d, 0) + 1
    return max(votes, key=votes.get) if votes else next(iter(config.DOMAINS))


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _keywords(value) -> list[str]:
    out = []
    for k in _as_list(value):
        k = str(k).strip().lower()[:40]
        if k and k not in out:
            out.append(k)
    return out[:6]
