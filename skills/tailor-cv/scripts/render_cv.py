#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rendercv[full]==2.8",
# ]
# ///

"""Render a RenderCV YAML file to PDF without altering CV facts.

Usage (project-independent recipe invocation from any caller directory):
    uv run --no-project /absolute/skill/scripts/render_cv.py INPUT --output PDF

Direct Python also works when RenderCV 2.8 is already installed:
    python scripts/render_cv.py INPUT --output PDF

Uses the real `rendercv render` CLI with discovered flags
(`--output-folder`, `--pdf-path`, `--dont-generate-markdown`,
`--dont-generate-png`; see `rendercv render --help`). Enforces
self-contained, built-in-theme-only YAML before RenderCV loads it.

Isolated generation prevents stale-PDF false passes: the PDF is built in a
temporary directory, verified (nonzero render exit rejected, exists, `%PDF`
header, non-empty), then published with exclusive creation. The already
inspected YAML/JSON text is written verbatim to an exclusive temporary
snapshot file and that snapshot path is passed to `rendercv render`; the
original caller-controlled path is never re-read by RenderCV (TOCTOU safe).
Returns 0 only on actual success; nonzero with actionable stderr otherwise.
Exit codes: 2 missing/unsupported input, 3 safety rejection, 4 missing
dependency, 1 general/read/render/write failure. Never modifies
the input or overwrites an existing output.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow direct `python scripts/render_cv.py` (deps preinstalled)
# or `uv run --no-project <abs path>/render_cv.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _safety import SafetyDependencyError, SafetyError, assert_safe_yaml_text

ALLOWED_INPUT_SUFFIXES = {".yaml", ".yml", ".json"}
# Discovered via `rendercv render --help` (RenderCV 2.8).
ISOLATED_PDF_NAME = "isolated.pdf"
RENDER_TIMEOUT_SECONDS = 120


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render RenderCV YAML to PDF via isolated temporary generation."
    )
    parser.add_argument("input", help="Path to the RenderCV YAML file.")
    parser.add_argument(
        "--output",
        required=True,
        help="Destination PDF path. Must not exist; never overwritten.",
    )
    return parser.parse_args(argv)


def fail(message: str, code: int = 1) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return code


def render_log_tail(proc: subprocess.CompletedProcess[str]) -> str:
    detail = (proc.stdout.strip() + "\n" + proc.stderr.strip()).strip()
    return detail[-2000:] if detail else "no CLI output captured"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists() or not input_path.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        print("Provide an existing .yaml/.yml/.json RenderCV file.", file=sys.stderr)
        return 2
    if input_path.suffix not in ALLOWED_INPUT_SUFFIXES:
        return fail(
            f"unsupported input extension {input_path.suffix!r} for {args.input}. "
            "Expected .yaml, .yml, or .json.",
            2,
        )
    if output_path.suffix.lower() != ".pdf":
        return fail(
            f"output must use a .pdf extension: {args.output}. "
            "Example: python scripts/render_cv.py examples/source_cv.yaml "
            "--output /tmp/tailored_cv.pdf",
            2,
        )

    if output_path.is_symlink() or output_path.exists():
        return fail(
            f"output already exists or is a symlink: {args.output}. Refusing to "
            "overwrite; choose a fresh per-application path or remove it explicitly."
        )

    try:
        input_resolved = input_path.resolve()
        output_resolved = output_path.resolve()
    except OSError as exc:
        return fail(f"cannot resolve paths: {exc}")

    if output_resolved == input_resolved:
        return fail(
            f"output {args.output} resolves to the same file as input {args.input}; "
            "refusing to overwrite the source. Choose a fresh per-application output path."
        )

    try:
        raw = input_path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            return fail(
                f"cannot read input file {args.input}: not valid UTF-8 ({exc}). "
                "Provide a UTF-8 encoded .yaml/.yml/.json file."
            )
    except OSError as exc:
        return fail(f"cannot read input file {args.input}: {exc}")

    try:
        assert_safe_yaml_text(text)
    except SafetyDependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 4
    except SafetyError as exc:
        return fail(f"unsafe RenderCV YAML: {exc}", 3)

    rendercv_bin = shutil.which("rendercv")
    if rendercv_bin is None:
        print(
            "Error: `rendercv` CLI not found on PATH. "
            f"Re-run with `uv run --no-project {Path(__file__).resolve()} INPUT "
            "--output <absolute-path>.pdf` so inline dependencies install automatically.",
            file=sys.stderr,
        )
        return 4

    try:
        output_resolved.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return fail(f"cannot create output directory {output_resolved.parent}: {exc}")

    with tempfile.TemporaryDirectory(prefix="tailor-cv-render-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        # TOCTOU-safe snapshot: render the exact bytes already inspected above.
        # The caller-controlled original path is never passed to RenderCV.
        snapshot_path = tmpdir_path / f"input_snapshot{input_path.suffix}"
        try:
            snapshot_path.write_bytes(raw)
        except OSError as exc:
            return fail(f"cannot stage inspected input for rendering: {exc}")
        isolated_pdf = tmpdir_path / ISOLATED_PDF_NAME
        cmd = [
            rendercv_bin,
            "render",
            str(snapshot_path),
            "--output-folder",
            str(tmpdir_path),
            "--pdf-path",
            str(isolated_pdf),
            "--dont-generate-markdown",
            "--dont-generate-png",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=RENDER_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            print(
                f"Error: failed to execute `rendercv`: {exc}. "
                f"Re-run with `uv run --no-project {Path(__file__).resolve()} INPUT "
                "--output <absolute-path>.pdf` so inline dependencies install automatically.",
                file=sys.stderr,
            )
            return 4
        except subprocess.TimeoutExpired:
            return fail(
                f"`rendercv render` timed out after {RENDER_TIMEOUT_SECONDS}s; "
                "no PDF was published."
            )

        if proc.returncode != 0:
            print(
                f"Error: rendering failed for {args.input} "
                f"(rendercv exit {proc.returncode}); no PDF was published.\n"
                f"RenderCV output:\n{render_log_tail(proc)}",
                file=sys.stderr,
            )
            return 1
        if not isolated_pdf.exists():
            print(
                f"Error: rendering failed; no PDF was generated for {args.input}.\n"
                f"RenderCV output:\n{render_log_tail(proc)}",
                file=sys.stderr,
            )
            return 1
        try:
            pdf_bytes = isolated_pdf.read_bytes()
        except OSError as exc:
            return fail(f"generated PDF is unreadable: {exc}")
        if len(pdf_bytes) < 200:
            return fail(
                f"generated PDF is suspiciously small ({len(pdf_bytes)} bytes); "
                f"refusing to publish.\nRenderCV output:\n{render_log_tail(proc)}"
            )
        if not pdf_bytes.startswith(b"%PDF"):
            return fail(
                "generated file is missing a %PDF header; refusing to publish.\n"
                f"RenderCV output:\n{render_log_tail(proc)}"
            )

        try:
            with open(output_resolved, "xb") as dst:
                dst.write(pdf_bytes)
        except FileExistsError:
            return fail(
                f"output already exists: {args.output}. Refusing to overwrite; "
                "choose a fresh per-application path or remove it explicitly."
            )
        except OSError as exc:
            try:
                output_resolved.unlink()
            except OSError:
                pass
            return fail(f"cannot publish PDF to {args.output}: {exc}")

    print(f"Rendered PDF: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
