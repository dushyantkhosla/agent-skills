"""Utility functions: user input, validation, sanitization."""

import os
import re
import shutil
import sys
from pathlib import Path


def prompt_user() -> str:
    return input("Enter the path to a local mp3 🎵 file or a full Youtube 🔗 link :: ").strip()


def is_youtube_url(text: str) -> bool:
    return text.lower().startswith("http")


def sanitize_filename(name: str) -> str:
    """Remove/replace characters unsafe for filenames."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_') or "output"


def sanitize_for_pdf(text: str) -> str:
    """Replace common Unicode chars with ASCII equivalents for core PDF fonts."""
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2026": "...", "\u00a0": " ", "\u2022": "*",
    }
    for uni, asc in replacements.items():
        text = text.replace(uni, asc)
    return text.encode("latin-1", "replace").decode("latin-1")


def _check_cmd(cmd: str, name: str, install_hint: str) -> None:
    if shutil.which(cmd) is None:
        print(f"{name} is required but not found on PATH.", file=sys.stderr)
        print(f"Install it first: {install_hint}", file=sys.stderr)
        sys.exit(1)


def validate_environment() -> None:
    """Check all required CLI tools and env vars are in place."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY environment variable is not set.", file=sys.stderr)
        print('  export OPENROUTER_API_KEY="your-key-here"', file=sys.stderr)
        sys.exit(1)

    _check_cmd("ffmpeg", "ffmpeg", "brew install ffmpeg  (macOS)  or  apt install ffmpeg  (Linux)")
    _check_cmd("uv", "uv", "curl -LsSf https://astral.sh/uv/install.sh | sh")
    _check_cmd("lms", "lms (LM Studio CLI)", "Install LM Studio from https://lmstudio.ai")
