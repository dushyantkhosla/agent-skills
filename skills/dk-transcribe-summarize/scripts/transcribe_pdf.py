#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.32",
#     "yt-dlp",
#     "fpdf2>=2.8",
#     "mistune>=3",
# ]
# ///

"""Transcribe audio from YouTube/local files and output PDF + HTML + Markdown.

Run: uv run scripts/transcribe_pdf.py
"""

from __future__ import annotations

import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path

from config import LOCAL_MODEL_NAME, OUTPUT_BASE
from utils import (
    prompt_user,
    is_youtube_url,
    sanitize_filename,
    validate_environment,
)
from audio import download_audio
from llm import (
    transcribe,
    ensure_lmstudio_ready,
    unload_lmstudio_model,
    summarize,
    verify_summary,
)
from output import write_pdf, write_html, write_markdown


def main() -> None:
    validate_environment()
    user_input = prompt_user()
    if not user_input:
        print("No input provided.", file=sys.stderr)
        sys.exit(1)

    audio_path: Path | None = None
    title: str
    tempdir: Path | None = None
    model_name = LOCAL_MODEL_NAME
    model_loaded = False

    try:
        date_str = dt.date.today().isoformat()
        out_dir = Path(OUTPUT_BASE) / date_str
        out_dir.mkdir(parents=True, exist_ok=True)

        if is_youtube_url(user_input):
            print("Downloading audio from YouTube...")
            audio_path, title = download_audio(user_input)
            tempdir = audio_path.parent
        else:
            audio_path = Path(user_input)
            if not audio_path.exists():
                print(f"File not found: {audio_path}", file=sys.stderr)
                sys.exit(1)
            title = audio_path.stem

        print("Transcribing...")
        transcript = transcribe(audio_path)
        if not transcript.strip():
            print("Transcription returned empty.", file=sys.stderr)
            sys.exit(1)

        print("Preparing LM Studio for summarization...")
        ensure_lmstudio_ready(model_name)
        model_loaded = True

        print("Generating 100-word summary (local model)...")
        summary_100 = verify_summary(summarize(transcript, 100), "100-word")

        print("Generating 400-word summary (local model)...")
        summary_400 = verify_summary(summarize(transcript, 400), "400-word")

        base_name = sanitize_filename(title)
        pdf_path = out_dir / f"{base_name}.pdf"
        html_path = out_dir / f"{base_name}.html"
        md_path = out_dir / f"{base_name}.md"

        print("Writing PDF...")
        write_pdf(title, summary_100, summary_400, pdf_path)

        print("Writing HTML...")
        write_html(title, summary_100, summary_400, html_path)

        print("Writing Markdown...")
        write_markdown(title, summary_100, summary_400, transcript, md_path)

        print(f"\n📂 {out_dir}/")
        print(f"   ✅ PDF:  {base_name}.pdf")
        print(f"   ✅ HTML: {base_name}.html")
        print(f"   ✅ MD:   {base_name}.md")

    finally:
        if model_loaded:
            unload_lmstudio_model(model_name)
        if tempdir and tempdir.exists():
            shutil.rmtree(tempdir, ignore_errors=True)
        if audio_path and audio_path.exists() and audio_path.suffix == ".compressed.mp3" and not tempdir:
            audio_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
