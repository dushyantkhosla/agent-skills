# RenderCV notes

Mechanics for step 6–7 of `SKILL.md`. RenderCV owns schema, layout, and PDF generation; this skill owns facts. Verified against RenderCV 2.8 (`requires-python >= 3.12`); reassess deliberately before adopting a newer major version.

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

- No custom themes, no `create-theme` output, no typst/code extensions.
- No includes, imports, remote references, or settings that fetch the network or load local files/code.
- Reject unsafe configuration at the CLI boundary with a nonzero exit and actionable stderr; never execute hostile content to "see what happens".

## Frozen helper contracts (run inside the skill directory)

```sh
uv sync
uv run python scripts/validate_rendercv.py INPUT
uv run python scripts/render_cv.py INPUT --output OUTPUT.pdf
uv run python scripts/extract_cv.py INPUT --output OUTPUT.txt
```

- `validate_rendercv.py INPUT` validates without writing output; exit 0 only on valid input.
- `render_cv.py INPUT --output PDF` renders without altering CV facts; exit 0 only on a verified non-empty PDF. Generate in isolation (temporary directory), check existence/header/non-emptiness, then publish; never leave a stale PDF behind on failure.
- `extract_cv.py INPUT --output TEXT` accepts PDF/DOCX; `--output` may be omitted (writes stdout). Fails nonzero on empty/scanned, encrypted/unreadable, malformed, or unsupported input — with OCR-limitation guidance, never invented text.
- Helpers reject destination/source collisions and existing outputs unless an explicit overwrite contract applies, and never modify the input bytes.
- Helpers implement mechanics only — never tailoring policy, keyword decisions, or claim judgments.

## Validation is structural, not factual

A passing schema check proves the YAML is well-formed RenderCV, not that any career claim is true. Factual verification is the separate conservative claim audit in `references/evidence-rules.md` (source/confirmation vs. JD-only/unsupported), performed by the harness on every run. Never present validation success as a truthfulness guarantee.

## Environment

Package-local uv environment (`uv sync` inside the skill directory); pinned `rendercv==2.8`, `pypdf` only where PDF extraction requires it, stdlib `unittest` for tests. No global installs, no absolute machine-specific paths in commands or docs — the harness resolves the skill directory and runs the commands there.
