"""Utility functions: user input, validation, sanitization."""

import os
import re
import shutil
import sys
from pathlib import Path

from config import MAX_PROMPT_LENGTH


def prompt_user() -> str:
    return input("Enter the path to a local mp3 🎵 file or a full Youtube 🔗 link :: ").strip()


def is_youtube_url(text: str) -> bool:
    """Check if text is a YouTube URL (not just any http URL)."""
    return bool(re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', text))


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


def parse_args() -> tuple[str | None, str, str | None]:
    """Parse CLI arguments for the hybrid transcription script.

    Returns (url_or_none, method, prompt_or_none).
    - url_or_none: YouTube URL or local path (None if not provided)
    - method: 'hybrid' (default), 'subtitles', or 'audio'
    - prompt_or_none: custom summary prompt (None if not provided)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Transcribe audio and generate summaries"
    )
    parser.add_argument(
        "url", nargs="?", default=None,
        help="YouTube URL or local audio file path"
    )
    parser.add_argument(
        "--method", choices=["hybrid", "subtitles", "audio"],
        default="hybrid",
        help="Transcription method (default: hybrid)"
    )
    parser.add_argument(
        "--prompt", type=str, default=None,
        help="Custom summarization instruction (overrides 100/400-word defaults)"
    )
    args = parser.parse_args()

    # Validate prompt length
    if args.prompt and len(args.prompt) > MAX_PROMPT_LENGTH:
        print(
            f"Error: --prompt must be {MAX_PROMPT_LENGTH} characters or fewer "
            f"(got {len(args.prompt)}).",
            file=sys.stderr,
        )
        sys.exit(1)

    return args.url, args.method, args.prompt
