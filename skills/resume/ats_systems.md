# ATS Systems — How They Work

Applicant Tracking Systems (Greenhouse, Lever, Workday, Taleo) parse resumes
into structured fields and rank by keyword/requirement match before a human
ever sees them. Goal: pass the parse cleanly and match the JD's language.

## Formatting rules (parser-safe)
- **No tables, text boxes, columns, or headers/footers** for content — parsers
  mangle or drop them. Single-column, top-to-bottom flow.
- Standard section headings: "Experience", "Education", "Skills", "Projects".
- Use a common font; no images, icons, or graphics for real content.
- Submit `.docx` or text-based `.pdf` (not scanned/image PDF).
- Dates in a consistent format (e.g. "Jan 2022 – Present").
- Don't hide keywords in white text — modern ATS and recruiters flag it.

## Keyword placement priority zones (highest signal first)
1. Job title / headline line.
2. Skills section (exact tool/tech names: "Kubernetes", "BGP", "Terraform").
3. Most recent role's bullets.
4. Summary statement.
Match the JD's **exact phrasing** — if it says "CI/CD" don't only write "build pipelines".

## What ATS scores on
- Hard-requirement keyword presence (must-haves).
- Years of experience signals matching the JD.
- Title/seniority alignment.
- Skills overlap density.

## Acronym handling
Include both the acronym and expansion once: "Border Gateway Protocol (BGP)",
"Service Level Objective (SLO)" — covers either search term.

## Honest tailoring (do / don't)
- DO surface real experience using the JD's vocabulary.
- DO reorder/emphasise relevant skills already present.
- DON'T invent experience or claim tools never used — it fails the interview.
- DON'T keyword-stuff; bullets must read naturally to a human.
