#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rendercv[full]==2.8",
# ]
# ///

"""Validate a RenderCV YAML file without writing any output.

Usage (project-independent recipe invocation from any caller directory):
    uv run --no-project /absolute/skill/scripts/validate_rendercv.py INPUT

Direct Python also works when RenderCV 2.8 is already installed:
    python scripts/validate_rendercv.py INPUT

Uses the verified RenderCV 2.8 API
``build_rendercv_dictionary_and_model`` (there is no `validate` CLI
subcommand). Enforces self-contained, built-in-theme-only YAML before
RenderCV loads it. Returns 0 only on actual validation success; nonzero
with actionable stderr otherwise. Exit codes: 2 missing/unsupported input,
3 safety rejection, 4 missing dependency, 1 general/read/validation failure.
Never modifies the input file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow direct `python scripts/validate_rendercv.py` (deps preinstalled)
# or `uv run --no-project <abs path>/validate_rendercv.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _safety import SafetyDependencyError, SafetyError, assert_safe_yaml_text

ALLOWED_INPUT_SUFFIXES = {".yaml", ".yml", ".json"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate RenderCV YAML (no output files are written)."
    )
    parser.add_argument("input", help="Path to the RenderCV YAML file.")
    return parser.parse_args(argv)


def format_validation_error(exc: Exception) -> str:
    """Format RenderCV/pydantic/YAML failures as actionable one-per-line text."""
    errors = getattr(exc, "validation_errors", None)
    if isinstance(errors, list) and errors:
        lines = []
        for err in errors[:10]:
            location = getattr(err, "schema_location", None) or getattr(
                err, "loc", None
            )
            message = getattr(err, "message", None) or str(err)
            prefix = f"{location}: " if location else ""
            lines.append(f"- {prefix}{message}")
        if len(errors) > 10:
            lines.append(f"- ... and {len(errors) - 10} more")
        return "\n".join(lines)
    message = str(exc).strip()
    return message if message else f"{exc.__class__.__name__} (see input file)"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(args.input)

    if not input_path.exists() or not input_path.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        print(
            "Provide an existing .yaml/.yml/.json RenderCV file.",
            file=sys.stderr,
        )
        return 2
    if input_path.suffix not in ALLOWED_INPUT_SUFFIXES:
        print(
            f"Error: unsupported input extension {input_path.suffix!r} for {args.input}. "
            "Expected .yaml, .yml, or .json.",
            file=sys.stderr,
        )
        return 2

    try:
        text = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        print(
            f"Error: cannot read input file {args.input}: not valid UTF-8 ({exc}). "
            "Provide a UTF-8 encoded .yaml/.yml/.json file.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Error: cannot read input file {args.input}: {exc}", file=sys.stderr)
        return 1

    try:
        assert_safe_yaml_text(text)
    except SafetyDependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 4
    except SafetyError as exc:
        print(f"Error: unsafe RenderCV YAML: {exc}", file=sys.stderr)
        return 3

    try:
        from rendercv.schema.rendercv_model_builder import (
            build_rendercv_dictionary_and_model,
        )
    except ImportError as exc:
        print(
            "Error: RenderCV 2.8 is required but could not be imported. "
            f"Re-run with `uv run --no-project {Path(__file__).resolve()} INPUT` "
            "so its inline dependencies install automatically. "
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 4

    try:
        build_rendercv_dictionary_and_model(text, input_file_path=input_path.resolve())
    except Exception as exc:
        detail = format_validation_error(exc)
        print(
            f"Error: invalid RenderCV YAML in {args.input}:\n{detail}", file=sys.stderr
        )
        return 1

    print(f"Valid RenderCV YAML: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
