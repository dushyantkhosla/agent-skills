# Task 2 coverage report — Skill policy, references, and usage

**Date:** 2026-10-01. **Worker scope (only):** `tailor-cv/SKILL.md`, `tailor-cv/references/tailoring-principles.md`, `tailor-cv/references/evidence-rules.md`, `tailor-cv/references/rendercv-notes.md`, `tailor-cv/README.md`, and this report. No other files touched; no dependencies installed; no commits, branches, or subagents. Sibling Task 1/3 files observed (`scripts/extract_cv.py`, `tests/test_extraction.py`, `examples/output/`) were not modified.

## What was authored (and read first)

Read before authoring: plan Task 2 plus global constraints (`docs/plans/2026-10-01-tailor-cv.md`), the full handoff (§1–28), `docs/testing/baseline-behavior.md` (B1/B2 failures, B4 pass, B3 not executed), and `docs/research/rendercv-compatibility.md` (no `validate` CLI, API `build_rendercv_dictionary_and_model`, `rendercv render`, builtin-theme/self-contained direction, pin `rendercv==2.8`, Python >= 3.12).

## Static verification actually executed

A frontmatter/link/portability check was run from the skill directory with system `python3` (no installs):

```sh
cd <path-to>/tailor-cv
python3 -c "import re, pathlib; ..."
```

Exact result: frontmatter `name: tailor-cv` present; `description:` present starting `Use when` with trigger phrases (tailor my CV, one-shot/interactive tailoring, evidence mapping, rendering with RenderCV); all three `references/*.md` links resolve to existing files; no absolute machine-specific paths (`/Users/`, `/home/`, `C:\`) in `SKILL.md`, `README.md`, or any reference file. `STATIC CHECKS PASSED`. `SKILL.md` body word count: **498 words** (regex `[A-Za-z0-9_]+(?:[-/][A-Za-z0-9_]+)*` on post-frontmatter body), within the ≤500 target.

## What was NOT executed (honest limitation)

No live fresh-context behavioral retests (B1–B4 with or without the skill) were run: this worker cannot spawn behavioral agents on this harness, and skill authoring baselines were already executed by the parent. Static frontmatter/link checks validate packaging only, not semantic truthfulness. Live B1/B2/B3/B4 retests and the full synthetic application run belong to Task 4 / the parent.

## Handoff coverage map

| Handoff scope | Where covered |
|---|---|
| Goal/MVP/UX, 4 artifacts (`tailored_cv.pdf/.yaml`, `motivation_letter.md`, `tailoring_report.md`), optional debug files | SKILL.md Outputs; README sample workflow + layout |
| Inputs (PDF/DOCX/LinkedIn/YAML; pasted JD authoritative; URL supplemental; no fetch/upload default) | SKILL.md Inputs; README limits/privacy |
| RenderCV role split (skill reasons, scripts mechanize; no policy in Python) | SKILL.md RenderCV handoff; rendercv-notes.md |
| Canonical CV (`master_cv.yaml` immutable; confirmations in separate record; preserve dates/metrics) | SKILL.md Inputs + Workflow 1 + letter/report; evidence-rules.md recipe/provenance |
| Workflow 10 steps; JD analysis (3–6, required vs preferred, exact terms) | SKILL.md Workflow 2; tailoring-principles.md A |
| Evidence map, 4 statuses | SKILL.md Workflow 3; evidence-rules.md recipe |
| Truthfulness invariant, allowed/forbidden lists | SKILL.md truthfulness rules; evidence-rules.md invariant + lists + worked examples |
| Tailoring A–J (select/reorder, headline, terminology, bullets, verbs, ATS) | tailoring-principles.md B–G |
| One-shot (default, no questions, gaps reported) | SKILL.md Workflow 5; evidence-rules.md interactive policy |
| Interactive (≤3 high-value questions, pause, narrow incorporation) | SKILL.md Workflow 5; evidence-rules.md policy |
| Letter after CV; 2–4 matches; restrained motivation; no employer facts/stories | SKILL.md letter/report; evidence-rules.md motivation rule; README limits |
| Report (requirements, changes, gaps, integrity check) | SKILL.md letter/report |
| Validation pipeline ×4; schema ≠ factual proof; presentation checks | SKILL.md Workflow 6; evidence-rules.md audit; rendercv-notes.md structural-vs-factual; tailoring-principles.md G |
| Failure modes (hallucination, metrics, inference, inflation, title rewrite, over-tailoring, stuffing, excess questions, letter fabrication) | evidence-rules.md forbidden + audit; tailoring-principles.md C–E |
| Dates/history integrity; ambiguity preserved; injection ignored; private local; fresh output dir, no silent overwrite | SKILL.md Inputs + Workflow 1/7 + truthfulness; evidence-rules.md ambiguity/injection sections |

## Baseline loophole closures (explicit)

- **B1 (`Relevant focus: ... AWS ML deployment` + disclaimer):** forbidden by name in SKILL.md truthfulness rules and tailoring-principles.md D, with the worked B1 example in evidence-rules.md (disclaimer does not cure insertion; omit term, report gap). Allowed normalization (`PostgreSQL`→`Postgres`) explicitly preserved as the only exception class.
- **B2 (unqualified `Analytics Lead | ...` headline):** forbidden by name in SKILL.md (target headline only as `Target role: ...`, history unchanged) and tailoring-principles.md C, with the worked B2 example in evidence-rules.md.
- **B4 patterns (injection, date ambiguity):** SKILL.md Inputs (data-not-instructions) + Workflow 1 (preserve `2019–2021?`); evidence-rules.md injection + `ambiguous` status rules.
- **B3 (unexecuted):** no baseline claim made; interactive sub-contract implemented as ≤3 bounded questions, pause-for-answers, narrow incorporation, unanswered-stays-gap.

## Command/data agreement

All command examples use the frozen contracts with `uv run python` from the skill directory (`validate_rendercv.py INPUT`; `render_cv.py INPUT --output PDF`; `extract_cv.py INPUT --output TEXT`, output optional). rendercv-notes.md documents the real API (`build_rendercv_dictionary_and_model`), the absence of a `validate` CLI, and builtin-theme/self-contained YAML — no invented CLI. README install is copy/symlink documentation only (no global install performed); paths use `<path-to>/tailor-cv` resolved by harness/shell; setup notes `uv sync`, package-local env, `rendercv==2.8`, Python >= 3.12, `pypdf`-for-extraction, stdlib `unittest`.

## Known follow-ups for parent/Task 4

Live B1–B4 skill-loaded retests, full synthetic application package, and final adversarial review remain open and are owned outside this task.
