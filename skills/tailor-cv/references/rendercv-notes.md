# RenderCV notes

Mechanics for the publish step of `SKILL.md`. RenderCV owns schema, layout, and PDF generation; this skill owns facts. Verified against RenderCV 2.8; reassess deliberately before adopting a newer major version.

## What RenderCV actually provides

- There is **no `rendercv validate` CLI subcommand**. `rendercv --help` lists `render`, `new`, and `create-theme` only. Do not invent or document a validate CLI.
- Programmatic validation uses the installed Python API:

```python
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model

data, model = build_rendercv_dictionary_and_model(yaml_text)
```

It parses/merges YAML and validates it into `RenderCVModel` (fields `cv`, `design`, `locale`, `settings`). Rendering (`rendercv render`) runs the same validation as part of generation; it is not a validate-only command.

- Minimal YAML accepted by the validator:

```yaml
cv:
    name: Jane Doe
```

- Full schema and themes are owned by RenderCV (`https://docs.rendercv.com`). Do not copy the schema into this package.

## Self-contained YAML constraint

Use built-in themes only. Constrain every user-provided or generated YAML document to ordinary, self-contained content before any validation or rendering:

- No `cv.photo`: the minimal ATS-readable MVP omits photos. Helpers reject all nonempty `cv.photo` values (any string, including a bare relative filename like `profile.jpg`); omit the photo entirely.
- No custom themes, no `create-theme` output, no typst/code extensions.
- No includes, imports, or remote references; no `settings.render_command` keys that pull in external YAML (`design`, `locale`, `locale_catalog`, `settings`).
- No output-path overrides in YAML (`output_folder`, `typst_path`, `pdf_path`, `markdown_path`, `html_path`, `png_path`): output locations come only from the helper `--output` argument.
- Reject unsafe configuration at the CLI boundary with a nonzero exit and actionable stderr; never execute hostile content to "see what happens".

## Frozen helper contracts

The agent stays in the caller project and resolves the absolute skill folder from the loaded `SKILL.md` location (never assume a fixed install path). Scripts carry inline pinned dependencies (PEP 723), so no `python` appears between `uv` options and the script path. All paths below are symbolic placeholders — resolve the skill path and the workspace paths to absolute literals before executing, without shell variable substitution:

```sh
uv run --no-project "/resolved/skill/scripts/validate_rendercv.py" "/absolute/workspace/master-or-tailored.yaml"
uv run --no-project "/resolved/skill/scripts/render_cv.py" "/absolute/workspace/tailored_cv.yaml" --output "/absolute/workspace/output/tailored_cv.pdf"
uv run --no-project "/resolved/skill/scripts/extract_cv.py" "/absolute/workspace/output/tailored_cv.pdf" --output "/absolute/workspace/output/extracted_cv.txt"
```

Helper input is `.yaml`/`.yml`/`.json`; there is no JSON5 input variant. Each command above shows its full contract: `validate_rendercv.py` takes only INPUT, `render_cv.py` requires `--output PDF`, and only `extract_cv.py --output` may be omitted (writes stdout).

- `validate_rendercv.py INPUT` validates without writing output; exit 0 only on valid input. Exit codes: 2 missing/unsupported input, 3 safety rejection, 4 missing dependency, 1 general/read/validation failure.
- `render_cv.py INPUT --output PDF` renders without altering CV facts; exit 0 only on a verified non-empty PDF. The exact inspected bytes are written to an exclusive temporary snapshot file and that snapshot is rendered (the original path is never re-read). Generate in isolation (temporary directory), check existence/header/non-emptiness including the captured RenderCV log on tiny/missing-header failures, then publish; never leave a stale PDF behind on failure. Exit codes: 2 missing/unsupported input, 3 safety rejection, 4 missing dependency, 1 general/read/render/write failure.
- `extract_cv.py INPUT --output TEXT` accepts PDF/DOCX; `--output` may be omitted (writes stdout). Fails nonzero on empty/scanned, encrypted/unreadable, malformed, or unsupported input — with OCR-limitation guidance, never invented text.
- Helpers reject destination/source collisions and existing outputs unless an explicit overwrite contract applies, and never modify the input bytes.
- Helpers implement mechanics only — never tailoring policy, keyword decisions, or claim judgments.

## Validation is structural, not factual

A passing schema check proves the YAML is well-formed RenderCV, not that any career claim is true. Factual verification is the separate conservative claim audit in `references/evidence-rules.md` (source/confirmation vs. JD-only/unsupported), performed by the harness on every run. Never present validation success as a truthfulness guarantee. Never promise ATS outcomes; only evidence-backed observable checks (actual `pypdf` extraction of the rendered PDF) and conventional design recommendations may be stated.

## Uncertain dates (RenderCV 2.8)

Range entries (`experience`, `education`, `projects`) require `start_date`/`end_date` as ExactDate (`YYYY-MM-DD`/`YYYY-MM`/`YYYY`/`present`). Never put free text there. For an uncertain range, omit both and use the single free-text `date` field only, preserving the `?`:

```yaml
cv:
    name: Taylor Morgan
    sections:
        experience:
            - company: Northstar Retail
              position: Analyst
              date: "2019–2021? (end year unclear)"
              location: Austin, TX
              summary: Operations reporting support.
              highlights:
                  - Built dashboards for operations.
```

This validates and renders with the `?` preserved. Never invent a parseable year to satisfy the schema.

## Environment

Helpers carry inline pinned dependencies and run via `uv run --no-project` with absolute paths; the agent never initializes a Python project, activates an environment, or modifies the caller workspace beyond writing requested outputs. Check `uv` is available before publishing; first use may download dependencies and Python into the `uv` cache — that cached environment is an implementation detail, not a setup step. A missing tool, helper, or network/permission surfaces as an actionable dependency requirement; never silently fall back to unvalidated rendering or global installs.
