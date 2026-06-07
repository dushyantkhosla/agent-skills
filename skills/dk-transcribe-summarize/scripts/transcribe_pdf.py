#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.32",
#     "yt-dlp",
#     "fpdf2>=2.8",
#     "mistune>=3",
#     "webvtt-py>=0.5",
#     "langdetect>=1.0",
#     "mlx-whisper>=0.4",
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
    parse_args,
)
from audio import (
    download_audio,
    get_subtitles,
    get_video_duration,
    check_subtitle_quality,
    parse_vtt,
    count_words,
)
from llm import (
    transcribe_with_fallback,
    TranscriptionFailed,
    summarize_custom,
    ensure_lmstudio_ready,
    unload_lmstudio_model,
    summarize,
    verify_summary,
)
from output import write_pdf, write_html, write_markdown, write_custom_output


def main() -> None:
    validate_environment()

    url, method, custom_prompt = parse_args()
    if url is None:
        url = prompt_user()
    if not url:
        print("No input provided.", file=sys.stderr)
        sys.exit(1)

    tempdirs: list[Path] = []
    model_loaded = False

    try:
        transcript: str = ""
        source: str = ""
        source_detail: str = ""
        title: str = ""
        metadata: dict = {}

        if is_youtube_url(url):
            if method in ("hybrid", "subtitles"):
                # STAGE 1: Try subtitles
                vtt_path, subs_tempdir, lang = get_subtitles(url)
                if subs_tempdir:
                    tempdirs.append(subs_tempdir)

                if vtt_path:
                    duration = get_video_duration(url)
                    quality = check_subtitle_quality(vtt_path, duration)
                    if quality == "good":
                        transcript = parse_vtt(vtt_path)
                        source = "subtitles"
                        wpm = int((count_words(vtt_path) / duration) * 60)
                        source_detail = f"YouTube auto-captions, {wpm} WPM"
                        print(f"✅ Transcribed via subtitles ({wpm} WPM, good quality)")
                        print(f"   Duration: {duration//60}:{duration%60:02d} | Words: {count_words(vtt_path)}")
                    elif method == "subtitles":
                        print("❌ No usable English subtitles found.")
                        print("   Try --method hybrid or --method audio.")
                        sys.exit(1)
                    else:
                        print(f"⚠️ Subtitles {quality} → falling back to audio")

                if not transcript and method == "subtitles":
                    print("❌ No English subtitles available for this video.")
                    print("   Try --method hybrid or --method audio.")
                    sys.exit(1)

            if not transcript:
                # Fall through to audio chain
                print("Downloading audio from YouTube...")
                audio_path, title, metadata = download_audio(url)
                tempdirs.append(audio_path.parent)

                print("Transcribing...")
                transcript, last_used_model = transcribe_with_fallback(audio_path)
                source = "audio"
                source_detail = f"via {last_used_model}"
        else:
            # Local file — audio chain only
            audio_path = Path(url)
            if not audio_path.exists():
                print(f"File not found: {audio_path}", file=sys.stderr)
                sys.exit(1)
            title = audio_path.stem

            print("Transcribing...")
            transcript, last_used_model = transcribe_with_fallback(audio_path)
            source = "audio"
            source_detail = f"via {last_used_model}"

        # Validate we have something
        if not transcript or len(transcript.split()) < 50:
            print("❌ Transcription failed or too short", file=sys.stderr)
            sys.exit(1)

        # STAGE 2: Summarization
        print(f"Preparing LM Studio for summarization ({LOCAL_MODEL_NAME})...")
        ensure_lmstudio_ready(LOCAL_MODEL_NAME)
        model_loaded = True

        date_str = dt.date.today().isoformat()
        out_dir = Path(OUTPUT_BASE) / date_str
        out_dir.mkdir(parents=True, exist_ok=True)

        channel = metadata.get("channel", "")
        base_name = sanitize_filename(f"{channel}-{title}" if channel else title)

        if custom_prompt:
            print("Generating custom summary (local model)...")
            summary = summarize_custom(transcript, custom_prompt)
            write_custom_output(
                title, summary, transcript,
                out_dir / base_name,
                metadata, source, source_detail,
            )
        else:
            print("Generating 100-word summary (local model)...")
            summary_100 = verify_summary(
                summarize(transcript, 100), "100-word",
                transcript=transcript, words=100,
            )
            print("Generating 400-word summary (local model)...")
            summary_400 = verify_summary(
                summarize(transcript, 400), "400-word",
                transcript=transcript, words=400,
            )

            pdf_path = out_dir / f"{base_name}.pdf"
            html_path = out_dir / f"{base_name}.html"
            md_path = out_dir / f"{base_name}.md"

            print("Writing PDF...")
            write_pdf(title, summary_100, summary_400, pdf_path)

            print("Writing HTML...")
            write_html(title, summary_100, summary_400, html_path)

            print("Writing Markdown...")
            write_markdown(
                title, summary_100, summary_400, transcript,
                md_path, metadata=metadata,
                source=source, source_detail=source_detail,
            )

        print(f"\n📂 {out_dir}/")
        print(f"   ✅ PDF:  {base_name}.pdf")
        print(f"   ✅ HTML: {base_name}.html")
        print(f"   ✅ MD:   {base_name}.md")

    except TranscriptionFailed as e:
        print(f"\n❌ {e}", file=sys.stderr)
        print("\n   Suggestions:", file=sys.stderr)
        print("   - Ensure OPENROUTER_API_KEY is set", file=sys.stderr)
        print("   - Try a shorter video", file=sys.stderr)
        sys.exit(1)

    finally:
        if model_loaded:
            unload_lmstudio_model(LOCAL_MODEL_NAME)
        for td in tempdirs:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    main()
