#!/usr/bin/env python3
"""Render a RenderCV YAML file to PDF without altering CV facts.

Usage:
    python scripts/render_cv.py INPUT --output PDF

Uses the real `rendercv render` CLI with discovered flags
(`--output-folder`, `--pdf-path`, `--dont-generate-markdown`,
`--dont-generate-png`; see `rendercv render --help`). Enforces
self-contained, built-in-theme-only YAML before RenderCV loads it.

Isolated generation prevents stale-PDF false passes: the PDF is built in a
temporary directory, verified (exists, `%PDF` header, non-empty), then
published to `--output`. Returns 0 only on actual success; nonzero with
actionable stderr otherwise. Never modifies the input or overwrites an
existing output.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow `python scripts/render_cv.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _safety import SafetyError, assert_safe_yaml_text

ALLOWED_INPUT_SUFFIXES = {".yaml", ".yml", ".json", ".json5"}
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


def fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists() or not input_path.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        print(
            "Provide an existing .yaml/.yml/.json/.json5 RenderCV file.",
            file=sys.stderr,
        )
        return 2
    if input_path.suffix not in ALLOWED_INPUT_SUFFIXES:
        return fail(
            f"unsupported input extension {input_path.suffix!r} for {args.input}. "
            "Expected .yaml, .yml, .json, or .json5."
        )
    if output_path.suffix.lower() != ".pdf":
        return fail(
            f"output must use a .pdf extension: {args.output}. "
            "Example: python scripts/render_cv.py examples/source_cv.yaml "
            "--output examples/output/tailored_cv.pdf"
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
    if output_resolved.exists():
        return fail(
            f"output already exists: {args.output}. Refusing to overwrite; "
            "choose a fresh per-application path or remove it explicitly."
        )

    try:
        text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        return fail(f"cannot read input file {args.input}: {exc}")

    try:
        assert_safe_yaml_text(text)
    except SafetyError as exc:
        return fail(f"unsafe RenderCV YAML: {exc}")

    rendercv_bin = shutil.which("rendercv")
    if rendercv_bin is None:
        print(
            "Error: `rendercv` CLI not found on PATH. "
            "Run `uv sync` in tailor-cv, then `uv run python scripts/render_cv.py ...`.",
            file=sys.stderr,
        )
        return 4

    try:
        output_resolved.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return fail(f"cannot create output directory {output_resolved.parent}: {exc}")

    with tempfile.TemporaryDirectory(prefix="tailor-cv-render-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        isolated_pdf = tmpdir_path / ISOLATED_PDF_NAME
        cmd = [
            rendercv_bin,
            "render",
            str(input_resolved),
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
                "Run `uv sync` in tailor-cv first.",
                file=sys.stderr,
            )
            return 4
        except subprocess.TimeoutExpired:
            return fail(
                f"`rendercv render` timed out after {RENDER_TIMEOUT_SECONDS}s; "
                "no PDF was published."
            )

        if not isolated_pdf.exists():
            detail = (proc.stdout.strip() + "\n" + proc.stderr.strip()).strip()
            tail = detail[-2000:] if detail else "no CLI output captured"
            print(
                f"Error: rendering failed; no PDF was generated for {args.input}.\n"
                f"RenderCV output:\n{tail}",
                file=sys.stderr,
            )
            return 1
        try:
            pdf_bytes = isolated_pdf.read_bytes()
        except OSError as exc:
            return fail(f"generated PDF is unreadable: {exc}")
        if len(pdf_bytes) < 200:
            # PDFs below a few hundred bytes cannot hold a real CV page.
            return fail(
                f"generated PDF is suspiciously small ({len(pdf_bytes)} bytes); "
                "refusing to publish. See RenderCV output above."
            )
        if not pdf_bytes.startswith(b"%PDF"):
            return fail("generated file is missing a %PDF header; refusing to publish.")

        try:
            shutil.copyfile(isolated_pdf, output_resolved)
        except OSError as exc:
            return fail(f"cannot publish PDF to {args.output}: {exc}")

    if not output_resolved.exists():
        return fail(f"failed to publish PDF to {args.output}.")
    print(f"Rendered PDF: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
