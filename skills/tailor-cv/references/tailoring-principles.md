# Tailoring principles

Methodology for steps 2 and 5 of `SKILL.md`. Optimize for relevance, clarity, evidence, and ATS readability. Never invent to match.

## A. Start with employer priorities

- Extract 3–6 deduplicated core responsibilities that define the role, plus every other material required or preferred qualification — there is no cap on evaluated requirements. Do not treat every sentence equally, but do not drop an important requirement to fit a number.
- Separate **required** from **preferred** qualifications. Never promote a preferred item into a hard requirement.
- Weight repeated skills, early-listed requirements, role-title language, and unusually detailed responsibilities.
- Capture exact terminology (tools, frameworks, methods, credentials, domain terms) for use only where evidence supports it.

## B. Select and reorder by relevance

- Tailoring is partly subtraction: remove or shorten impressive but irrelevant bullets when they compete with stronger evidence.
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

- Simple conventional structure, parseable sections, clear headings, conventional dates, relevant skills in context and in the skills section, minimal decorative complexity.
- Never promise ATS outcomes: do not claim the CV would pass a parse, earn a score, change a hiring decision, or be ATS-compatible. Only evidence-backed observable checks (actual `pypdf` text extraction of the rendered PDF proves readable text) and conventional design recommendations (simple structure, conventional headings, parseable sections) may be stated — never as parser-behavior or outcome guarantees. Ignore fictional ATS folklore (hidden text, exact keyword density tricks).

## G. Presentation sanity check (before returning)

Check length, duplicate bullets, awkward ordering, malformed dates, orphan headings, broken rendering, repetitive wording, keyword stuffing, and extraction artifacts. For an uncertain range, use the single free-text `date: "2019–2021? (end year unclear)"` with `start_date`/`end_date` omitted (see `evidence-rules.md`); never invent a parseable year to satisfy a schema. Repair structure only — never repair a gap by inventing a fact.
