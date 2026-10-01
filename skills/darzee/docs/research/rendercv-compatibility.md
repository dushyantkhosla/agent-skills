# RenderCV compatibility research

**Checked:** 2026-10-01. No packages were installed or updated.

## Local environment and workspace

- System `python3 --version`: **3.14.7**. `uv --version`: **0.8.22**.
- `rendercv --version`: **RenderCV v2.8**. The command resolves to `/Users/dush/.local/bin/rendercv`, a uv tool shim at `/Users/dush/.local/share/uv/tools/rendercv/bin/rendercv`; its shebang selects that tool environment’s **Python 3.13.7**. The system Python does not import RenderCV; use the CLI or that tool interpreter for API calls.
- PyPI JSON metadata (`https://pypi.org/pypi/rendercv/json`, fields `info.version` and `info.requires_python`): latest listed version **2.8**, requires Python **>=3.12**. Checked from metadata only.
- Existing sibling `~/.agents/skills/tailor-cv`: **absent**. Project `docs/` exists.
- Git status at inspection: branch `main` tracking `origin/main`; pre-existing `M ../.DS_Store` and `?? ./` (untracked project contents). Preserve these; no cleanup was performed.

## API and CLI constraints

- There is **no `validate` CLI subcommand**. `rendercv --help` lists `render`, `new`, and `create-theme` only.
- Validator: `rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model(main_yaml_file: str, *, input_file_path: pathlib.Path | None = None, **kwargs) -> tuple[CommentedMap, RenderCVModel]`. It parses/merges YAML and validates into `RenderCVModel`. Installed source: `.../rendercv/schema/rendercv_model_builder.py`, lines 193–211.
- The model is `rendercv.schema.models.rendercv_model.RenderCVModel`; fields are `cv`, `design`, `locale`, and `settings` (installed source lines 1–29). Minimal API validation succeeded with the YAML below.
- The render wrapper is `rendercv.cli.render_command.run_rendercv.run_rendercv(input_file_path, progress, **kwargs)`; it reads the file, calls the same validator, generates Typst, then PDF (and PNG/Markdown/HTML depending on options). Installed source: `.../rendercv/cli/render_command/run_rendercv.py`, lines 13–48. Prefer the supported CLI over calling this wrapper directly because it requires RenderCV’s progress object.
- CLI render command: `rendercv render INPUT_FILE_NAME [--output-folder PATH]`. `rendercv render --help` confirms output-path and generation flags. A successful `render` performs validation as part of rendering; it is not a validate-only command.

## Recommendation and minimal YAML

For reproducible behavior against the verified API, pin **`rendercv==2.8`** and document Python **>=3.12**. Reassess/pin deliberately before adopting a newer major version; the installed project API is verified only at 2.8. Example commands:

```sh
rendercv render tailored_cv.yaml --output-folder rendercv_output
```

For validation from Python (in the RenderCV environment):

```python
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model

data, model = build_rendercv_dictionary_and_model(yaml_text)
```

Minimal YAML accepted by the installed validator:

```yaml
cv:
  name: Jane Doe
```

## Evidence sources

- Local CLI: `rendercv --help`; `rendercv render --help`.
- Local installed source paths/signatures noted above (RenderCV 2.8, uv tool Python 3.13.7).
- PyPI project metadata: https://pypi.org/pypi/rendercv/json
- RenderCV docs: https://docs.rendercv.com (CLI help points to this documentation).
