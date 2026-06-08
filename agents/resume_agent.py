"""Resume / ATS agent — three modes:

  1. analyze   : resume + JD -> keyword gap report, ATS match score
  2. tailor    : resume + JD -> full rewrite weaving in missing keywords honestly
  3. cover_letter : resume + JD (+ tone) -> role-specific cover letter

File parsing (PDF/DOCX) is included but lazily imported so the module loads
even before those libs are installed. Results persist to the applications table.
"""
import json

from agents.base import load_skill, call_claude
from context.shared_context import SharedContext
import config

# ---------------------------------------------------------------- parsing
def parse_resume_file(path: str) -> str:
    """Extract plain text from a .pdf or .docx resume. Lazy imports."""
    lower = path.lower()
    if lower.endswith(".pdf"):
        from pdfminer.high_level import extract_text
        return extract_text(path).strip()
    if lower.endswith(".docx"):
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs).strip()
    if lower.endswith(".txt"):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    raise ValueError("Unsupported file type. Use .pdf, .docx, or .txt.")


# ---------------------------------------------------------------- prompts
ANALYZE_SYSTEM = """You are an ATS (Applicant Tracking System) screening expert.
Compare the candidate's resume against the job description and report honestly.

Use this reference on how ATS systems work:
{ats_skill}

Return ONLY valid JSON in this exact shape:
{{
  "ats_score": <0-100 integer estimate of keyword/requirement match>,
  "hard_requirements": [
    {{"requirement": "<text>", "status": "met" | "missing" | "weak",
      "evidence": "<where in resume, or 'absent'>"}}
  ],
  "keywords_present": ["<exact terms already in the resume>"],
  "keywords_missing": ["<important JD terms absent from the resume>"],
  "preferred_quals_missing": ["<nice-to-haves not present>"],
  "tone_signals": ["<culture/tone cues from the JD>"],
  "verdict": "<2-3 sentences: would this pass an initial ATS screen and why>"
}}"""

TAILOR_SYSTEM = """You are an expert resume writer. Rewrite the candidate's resume to
maximise match with this job description WITHOUT fabricating anything.

Reference material:
{ats_skill}

{writing_skill}

Hard rules:
- Never invent experience, tools, titles, employers, dates, or metrics.
- Only reframe REAL experience using the JD's vocabulary and exact keyword phrasing.
- Weave in the missing keywords ONLY where the candidate plausibly has that experience;
  if something is genuinely absent, do not fake it — note it at the end instead.
- Keep it single-column and ATS-safe (no tables/columns). Preserve the candidate's voice.
- Strengthen weak bullets with quantification where the resume implies a number.

Output format:
First the full tailored resume in plain text.
Then a line: ===NOTES===
Then a short bullet list of: (a) what you changed, (b) genuine gaps you could NOT
honestly fill and the candidate should address."""

COVER_SYSTEM = """You are an expert cover-letter writer.
Write a {tone} cover letter for this candidate and role.

Reference:
{writing_skill}

Rules:
- 3-4 short paragraphs. Open with a specific hook tied to the company/role
  (never "I am applying for...").
- Map 2-3 of the candidate's strongest, RELEVANT real experiences to the JD's needs.
- Match the JD's tone. Close with a confident, concrete ask.
- Do not fabricate. Only use what's in the resume."""


class ResumeAgent:
    # ---- mode 1: ATS analysis ----
    def analyze(self, ctx: SharedContext, resume_text: str, jd_text: str) -> dict:
        system = ANALYZE_SYSTEM.format(ats_skill=load_skill("ats"))
        raw = call_claude(
            system,
            [{"role": "user", "content": self._payload(resume_text, jd_text)}],
            max_tokens=config.MAX_TOKENS_LONG,
        )
        report = self._parse_json(raw)
        # Update shared context so the rest of the platform sees the gap state.
        ctx.active_jd = jd_text
        ctx.ats_keywords_found = report.get("keywords_present", [])
        ctx.ats_keywords_missing = report.get("keywords_missing", [])
        self._persist(ctx, jd_text, ats_score=report.get("ats_score"),
                      keywords_added=report.get("keywords_missing", []))
        return report

    # ---- mode 2: tailoring (full rewrite) ----
    def tailor(self, ctx: SharedContext, resume_text: str, jd_text: str) -> str:
        system = TAILOR_SYSTEM.format(
            ats_skill=load_skill("ats"), writing_skill=load_skill("resume_writing"))
        result = call_claude(
            system,
            [{"role": "user", "content": self._payload(resume_text, jd_text)}],
            max_tokens=config.MAX_TOKENS_LONG,
        )
        self._persist(ctx, jd_text, tailored_resume=result)
        return result

    # ---- mode 3: cover letter ----
    def cover_letter(self, ctx: SharedContext, resume_text: str, jd_text: str,
                     tone: str = "confident and professional") -> str:
        system = COVER_SYSTEM.format(tone=tone, writing_skill=load_skill("resume_writing"))
        letter = call_claude(
            system,
            [{"role": "user", "content": self._payload(resume_text, jd_text)}],
            max_tokens=config.MAX_TOKENS_LONG,
        )
        self._persist(ctx, jd_text, cover_letter=letter)
        return letter

    # ---- helpers ----
    @staticmethod
    def _payload(resume_text: str, jd_text: str) -> str:
        return (f"=== RESUME ===\n{resume_text}\n\n"
                f"=== JOB DESCRIPTION ===\n{jd_text}")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        try:
            start, end = raw.index("{"), raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"error": "Could not parse analysis", "raw": raw}

    @staticmethod
    def _persist(ctx: SharedContext, jd_text: str, **fields) -> None:
        """Best-effort upsert into applications. Never crash on DB error."""
        try:
            from db.connection import get_cursor
            cols = ["user_id", "jd_text"]
            vals = [ctx.user_id, jd_text]
            for k, v in fields.items():
                cols.append(k)
                vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
            placeholders = ", ".join(["%s"] * len(vals))
            with get_cursor(commit=True) as cur:
                cur.execute(
                    f"INSERT INTO applications ({', '.join(cols)}) VALUES ({placeholders})",
                    vals,
                )
        except Exception as e:  # pragma: no cover - DB optional in early dev
            print(f"  [warn] could not persist application to DB: {e}")
