# tailor-cv

A portable Agent Skill that turns a source CV plus a pasted job description into a truthful tailored application: `tailored_cv.pdf`, `tailored_cv.yaml`, `motivation_letter.md`, `tailoring_report.md`.

The harness (e.g. Codex, Claude Code) does the reasoning with `SKILL.md` plus `references/`; three small Python helpers do extraction, validation, and rendering. Helpers never decide tailoring policy. Requires Python >= 3.12, pinned `rendercv==2.8`, `pypdf` for PDF extraction, stdlib `unittest` — all inside a package-local uv environment.

## Setup

Run everything from the skill directory — the path below is resolved by your harness or shell, not a fixed location on any machine:

```sh
cd <path-to>/tailor-cv
uv sync
uv run python -m unittest discover -s tests -v
```

Manual checks:

```sh
uv run python scripts/validate_rendercv.py examples/source_cv.yaml
uv run python scripts/render_cv.py examples/source_cv.yaml --output examples/output/tailored_cv.pdf
uv run python scripts/extract_cv.py examples/output/tailored_cv.pdf --output examples/output/extracted_cv.txt
```

`extract_cv.py --output` may be omitted to write to stdout. Never run these commands from another directory and never substitute a global install: the environment is package-local (`uv sync` inside this folder).

## Manual installation into a harness

No automatic or global install is performed. To use the skill, copy or symlink this `tailor-cv/` folder into your harness's skills directory (consult your harness docs for the exact location), then invoke it by name:

> My CV is attached. Here is the job description. Use the `tailor-cv` skill and give me a tailored CV PDF and motivation letter as Markdown.

Modes: `Use one-shot mode. Do not ask me questions.` (default when unspecified) or `Use interactive mode and ask me if important evidence is missing.` (at most 3 targeted questions, then it pauses for your answers).

## Sample workflow

1. Attach CV (PDF, DOCX, LinkedIn PDF, or RenderCV YAML) and paste the full JD text.
2. The agent saves an immutable `master_cv.yaml`, analyzes 3–6 core requirements (required vs. preferred), and maps each to source evidence (`strong` / `partial` / `absent` / `ambiguous`).
3. It tailors selection, order, and wording around supported evidence only, validates the YAML, renders the PDF, then writes the letter and report into a fresh per-application output directory.
4. You receive the four artifacts plus explicit unresolved gaps (e.g. no AWS evidence, no 25% metric).

## Limits

- **Extraction:** deterministic text only, with page/block separation. No OCR: empty, scanned-image, encrypted, or malformed documents fail with guidance instead of invented text. Tables and reading order are best-effort; the agent preserves ambiguity rather than guessing.
- **Truthfulness:** missing evidence stays missing. The skill never invents technology, deployment, metrics, titles, scope, leadership, or motivation to match a JD — not under time pressure, not for ATS keywords, not on recruiter instructions. Schema validation passing means the YAML is well-formed, not that claims are true.
- **Motivation letter:** written after the CV from the same evidence. If you gave no reason for wanting the role, the letter uses restrained factual language (`interested in bringing X experience to Y`) — never invented passion, employer facts, or personal stories.
- **Privacy:** fully local by default. Documents are never uploaded and job sites never fetched unless you explicitly ask.

## Layout

`SKILL.md` · `references/` (policy detail) · `scripts/` (frozen CLIs) · `tests/` · `examples/`
