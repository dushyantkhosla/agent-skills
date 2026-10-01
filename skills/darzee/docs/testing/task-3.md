# Task 3 — Minimal document extraction: test report

Scope (owned files only): `tailor-cv/scripts/extract_cv.py`,
`tailor-cv/tests/test_extraction.py`, and this report. Sibling Task 1/2 files
were not touched.

## Environment

- System Python 3.14.7 (satisfies `>=3.12`).
- `pypdf` NOT installed in system Python; Task 1's package-local uv `.venv`
  / `pyproject.toml` / `uv.lock` did not exist yet at test time, so per the
  task brief I did **not** run `uv sync` (concurrent env ownership is Task 1's)
  and ran the stdlib-capable suite on system Python.
- PDF content tests skip cleanly without `pypdf` and a dependency-guidance
  test asserts the CLI reports the missing `pypdf`/Task 1 env blocker instead
  of silently succeeding. DOCX + CLI-safety tests run fully on stdlib.
- DOCX needs no new dependency: stdlib `zipfile` + `xml.etree.ElementTree`
  proved adequate (paragraphs + tables in document order), so no extra
  dependency to report.

## TDD red run (tests written before the script)

Command (workdir `darzee/tailor-cv`):

```sh
python3 -m unittest discover -s tests -v
```

Result: `Ran 23 tests — FAILED (failures=11, skipped=8)`.
All 11 failures were `can't open file '.../tailor-cv/scripts/extract_cv.py':
[Errno 2] No such file or directory` (script not yet written), e.g.:

```text
FAIL: test_docx_text_preservation (...TestDocxExtraction...)
AssertionError: 2 != 0 : ... can't open file '.../scripts/extract_cv.py': [Errno 2] No such file or directory
```

The 8 skips were the PDF tests (`pypdf not installed; Task 1 env pending`).
4 CLI-safety tests passed coincidentally (missing script already exits nonzero).

## Focused green run (Task 3 scope, after implementing the script)

Command:

```sh
python3 -m unittest discover -s tests -v
```

(At the time only `test_extraction.py` existed; the sibling rendering suite
landed afterwards — see next section.) Verbatim output:

```text
test_existing_destination_not_silently_overwritten (...TestCliSafety...) ... ok
test_help_documents_limitations (...TestCliSafety...) ... ok
test_input_directory_fails (...TestCliSafety...) ... ok
test_missing_input_fails (...TestCliSafety...) ... ok
test_output_collision_rejected (...TestCliSafety...) ... ok
test_output_to_directory_fails (...TestCliSafety...) ... ok
test_pdf_without_pypdf_reports_dependency (...TestCliSafety...) ... ok
test_unsupported_extension_fails (...TestCliSafety...) ... ok
test_docx_empty_fails (...TestDocxExtraction...) ... ok
test_docx_input_immutable (...TestDocxExtraction...) ... ok
test_docx_malformed_fails (...TestDocxExtraction...) ... ok
test_docx_stdout_mode (...TestDocxExtraction...) ... ok
test_docx_table_content_in_document_order (...TestDocxExtraction...) ... ok
test_docx_text_preservation (...TestDocxExtraction...) ... ok
test_docx_with_macro_blob_does_not_execute (...TestDocxExtraction...) ... ok
test_pdf_empty_fails_with_ocr_guidance (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_encrypted_fails (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_input_immutable (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_linkedin_style_preservation (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_malformed_fails (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_page_boundaries_preserved (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_partial_unreadable_page_fails (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'
test_pdf_text_preservation (...TestPdfExtraction...) ... skipped 'pypdf not installed; Task 1 env pending'

----------------------------------------------------------------------
Ran 23 tests in 0.624s

OK (skipped=8)
EXIT:0
```

## Full currently-available suite (includes sibling Task 1 tests)

Command: `python3 -m unittest discover -s tests -v`

Result: `Ran 41 tests — FAILED (failures=7, skipped=8)`.
All 15 runnable Task 3 tests pass; all 7 failures are in the sibling
`tests/test_rendering.py` (Task 1 scope) and are all of the form
`can't open file '.../scripts/render_cv.py'` /
`can't open file '.../scripts/validate_rendercv.py': [Errno 2]` —
Task 1 scripts not yet written. No Task 3 test fails. Left for Task 1;
not edited here.

## Syntax check

```sh
python3 -m compileall -q scripts tests && echo COMPILE-OK
```

Result: `COMPILE-OK`.

## Manual smoke check (stdlib DOCX, real CLI)

```text
$ python3 scripts/extract_cv.py /tmp/task3-smoke/cv.docx
Smoke Test Name

Skill A | Skill B

Trailing line
EXIT:0
$ python3 scripts/extract_cv.py /tmp/task3-smoke/cv.docx --output /tmp/task3-smoke/out.txt
EXIT:0
$ python3 scripts/extract_cv.py /tmp/task3-smoke/cv.docx --output /tmp/task3-smoke/out.txt
Error: refusing to overwrite existing destination '/tmp/task3-smoke/out.txt'. Remove it or choose a fresh path.
EXIT:1
```

Table cells linearize as `Skill A | Skill B` in document order between the
surrounding paragraphs; existing destinations are refused, not overwritten.

## Design notes

- Frozen CLI honored: `python scripts/extract_cv.py INPUT --output TEXT`,
  `--output` optional (stdout). No `--force`/overwrite flag added.
- PDF via `pypdf` only (`PdfReader`/`is_encrypted`/`pages`/`extract_text` —
  stable API, version locked by Task 1). Pages joined with
  `--- Page i of n ---` separators. Any blank/unreadable page (including
  partial) is a nonzero failure naming the page(s) with OCR-limitation
  guidance — never silent partial success. Encrypted PDFs fail with guidance
  to supply an unencrypted file.
- DOCX via stdlib only: body children walked in document order; `w:p` →
  text blocks, `w:tbl` rows → `cell | cell` lines; only `w:t`/`w:tab`/`w:br`
  contribute (field codes ignored as data, `vbaProject.bin` never read as
  code — macros cannot execute since nothing is ever evaluated).
- Guards: missing/unsupported input, non-file input, output==source
  collision (resolved-path compare), existing destination (checked before
  and after parent-dir creation), permission/`OSError` on read/write,
  empty-output refusal. `--help` documents reading-order ambiguity and the
  OCR limitation.
- Tests use tiny fixtures generated in-test (hand-built minimal PDFs,
  `zipfile`-built DOCXs) and the public CLI via subprocess with timeouts;
  no mocked PDF parsing.

## Concerns / follow-ups

1. **PDF path not yet executed against real `pypdf`** (blocker, declared):
   8 PDF tests skip on system Python. Once Task 1's `.venv` lands, rerun
   with `uv run python -m unittest discover -s tests -v` — no code changes
   expected, but the minimal-PDF fixture generator and `extract_text`
   assumptions must be confirmed green there.
2. **PDF reading-order ambiguity is harness responsibility** (per handoff §8
   and plan): the script preserves content-stream order with explicit page
   separators and documents the limitation in `--help`/docstring; the agent
   must verify extraction against the source before building RenderCV YAML.
3. No commits/branches/installs made; no sibling files or dependencies
   modified (`pypdf` addition, if the lock needs it, is flagged for the
   Task 1 env owner).
