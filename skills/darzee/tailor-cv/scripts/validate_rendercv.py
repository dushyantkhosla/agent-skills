#!/usr/bin/env python3
"""Validate a RenderCV YAML file without writing any output.

Usage:
    python scripts/validate_rendercv.py INPUT

Uses the verified RenderCV 2.8 API
``build_rendercv_dictionary_and_model`` (there is no `validate` CLI
subcommand). Enforces self-contained, built-in-theme-only YAML before
RenderCV loads it. Returns 0 only on actual validation success; nonzero
with actionable stderr otherwise. Never modifies the input file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/validate_rendercv.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _safety import SafetyError, assert_safe_yaml_text


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate RenderCV YAML (no output files are written)."
    )
    parser.add_argument("input", help="Path to the RenderCV YAML file.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(args.input)

    if not input_path.exists() or not input_path.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        print(
            "Provide an existing .yaml/.yml/.json/.json5 RenderCV file.",
            file=sys.stderr,
        )
        return 2
    if input_path.suffix not in {".yaml", ".yml", ".json", ".json5"}:
        print(
            f"Error: unsupported input extension {input_path.suffix!r} for {args.input}. "
            "Expected .yaml, .yml, .json, or .json5.",
            file=sys.stderr,
        )
        return 2

    try:
        text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot read input file {args.input}: {exc}", file=sys.stderr)
        return 1

    try:
        assert_safe_yaml_text(text)
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
            f"Run `uv sync` in tailor-cv first. Details: {exc}",
            file=sys.stderr,
        )
        return 4

    try:
        build_rendercv_dictionary_and_model(text, input_file_path=input_path.resolve())
    except Exception as exc:
        # RenderCV raises RenderCVUserValidationError with a structured
        # `validation_errors` list (str(exc) is often empty); surface those
        # details actionably without a traceback.
        detail = format_validation_error(exc)
        print(
            f"Error: invalid RenderCV YAML in {args.input}:\n{detail}", file=sys.stderr
        )
        return 1

    print(f"Valid RenderCV YAML: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
