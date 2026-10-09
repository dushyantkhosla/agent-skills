# Tailoring principles

Methodology for steps 2 and 5 of `SKILL.md`. Optimize for relevance, clarity, evidence, and ATS readability. Never invent to match.

## A. Start with employer priorities

- Extract 3–6 deduplicated core responsibilities that define the role, plus every other material required or preferred qualification — there is no cap on evaluated requirements. Do not treat every sentence equally, but do not drop an important requirement to fit a number.
- Separate **required** from **preferred** qualifications. Never promote a preferred item into a hard requirement.
- Weight repeated skills, early-listed requirements, role-title language, and unusually detailed responsibilities.
- Capture exact terminology (tools, frameworks, methods, credentials, domain terms) for use only where evidence supports it.

## B. Select and reorder by relevance

- Treat the source CV as an intentionally long evidence reservoir, not a draft whose full content must survive. Preserve the complete source in `master_cv.yaml`; select only JD-relevant evidence for the tailored CV, retaining essential career-history context.
- Tailoring is partly subtraction: remove or shorten impressive but irrelevant bullets when they compete with stronger evidence.
- Remove redundant facts and repetitive technology/skill lists. Each retained experience bullet should add distinct evidence, scope, or an outcome.
- Rephrase or combine related bullets within the same experience when useful, preserving attribution, metrics, scope, and uncertainty. Never merge claims across employers or imply relationships not supported by the source.
- Within each role, move the strongest job-relevant achievements to the top. Original order is not sacred.
- Reframe an existing achievement around a relevant outcome (e.g. forecasting work as planning support) without adding new facts.
- Adjacent experience may be emphasized (regulated-data experience for a healthcare role) but never renamed (fintech is not healthcare).

## C. Tailor the top of the first page

- Rewrite the summary and surface the most relevant skills so fit is obvious quickly.
- A truthful target headline is allowed only when explicitly labeled and visibly not a work-history title. Correct: `Target role: Analytics Lead`. Forbidden: an unqualified `Analytics Lead | Analytics, Reporting & Forecasting` headline that presents target seniority as candidate seniority.
- Never change historical employer, title, or date records to mirror the target role. `Data Analyst — Northstar Retail, 2021–2024` stays exactly that.

## D. Use employer terminology only where truthful

- Prefer exact JD terms for supported tools, methods, and credentials; use them naturally, once, in context.
- Equivalent normalization that changes no meaning is allowed (e.g. `PostgreSQL` → `Postgres`).
- Forbidden: inserting JD keywords solely to match (AWS, SageMaker, Kubernetes, Python), keyword-stuffed skills blocks, and `Relevant focus:` / `Relevant skills:` lines that smuggle unsupported technology next to a disclaimer (a trailing "not represented in my background" does not cure the inserted claim). If evidence is absent, omit the term and list the gap in the report.
- Do not make the CV read like a copy of the JD (over-tailoring).

## E. Write evidence-oriented bullets

- Prefer `Action + what was done + scope/context + outcome`. Quantify only with metrics already present in the source or explicitly confirmed in this conversation.
- Never force a number into every bullet; describe scope or outcome precisely when no metric exists.
- Demonstrate soft skills through accomplishments, not adjectives (`team player`, `strategic`, `self-starter` alone prove nothing).
- Use the verb that describes what the candidate actually did. `Contributed`, `helped`, `collaborated`, `participated` stay scoped; never upgrade to `owned`, `led`, `managed`, or `defined strategy` without evidence. Seniority must emerge from scope and outcomes, not verb inflation.

## F. Keep the result ATS-readable

- Simple conventional structure, parseable sections, clear headings, conventional dates, a concise relevant skills section and evidence-bearing experience bullets, minimal decorative complexity. Repeat a technology only when it adds meaningful context, not keyword padding.
- Never promise ATS outcomes: do not claim the CV would pass a parse, earn a score, change a hiring decision, or be ATS-compatible. Only evidence-backed observable checks (actual `pypdf` text extraction of the rendered PDF proves readable text) and conventional design recommendations (simple structure, conventional headings, parseable sections) may be stated — never as parser-behavior or outcome guarantees. Ignore fictional ATS folklore (hidden text, exact keyword density tricks).

## G. Presentation sanity check (before returning)

- The final rendered PDF must be at most two pages; verify the actual PDF page count, not an estimate from YAML or text.
- If it exceeds two pages, first tighten wording and combine related bullets; then drop up to five additional experience bullets across all roles, choosing redundant or lowest-relevance evidence first. This limit applies cumulatively to page-fit trimming after initial relevance selection, not to source filtering.
- Preserve unique evidence for high-priority JD requirements and readable typography. Preserve the supplied YAML `design:` section exactly unless the user explicitly asks to change it; it reflects their optimized aesthetic. Never meet the page limit by changing fonts, font sizes, spacing, margins, theme, or any other design setting. Fit by editing content, not design. Re-audit changed claims and re-render after revisions.
- If the PDF still exceeds two pages after these bounded revisions, report the constraint failure rather than presenting it as a finished deliverable. See `rendercv-notes.md` for the render/check/revision loop.

Check duplicate bullets, awkward ordering, malformed dates, orphan headings, broken rendering, repetitive wording, keyword stuffing, and extraction artifacts. For an uncertain range, use the single free-text `date: "2019–2021? (end year unclear)"` with `start_date`/`end_date` omitted (see `evidence-rules.md`); never invent a parseable year to satisfy a schema. Repair structure only — never repair a gap by inventing a fact.
