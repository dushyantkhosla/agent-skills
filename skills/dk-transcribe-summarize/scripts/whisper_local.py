"""Local transcription via mlx-whisper on Apple Silicon.

Uses the whisper-large-v3-turbo model already downloaded
by LM Studio at ~/.lmstudio/models/mlx-community/.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from config import WHISPER_MODEL_PATH


def whisper_transcribe(audio_path: Path) -> str:
    """Transcribe audio using local mlx-whisper.

    Returns the transcription text.
    Raises RuntimeError on any failure (caught by fallback chain).
    """
    # Pre-flight checks
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install: brew install ffmpeg")

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    size_bytes = audio_path.stat().st_size
    if size_bytes == 0:
        raise RuntimeError("Audio file is empty")

    size_mb = size_bytes / (1024 * 1024)
    if size_mb > 500:
        raise RuntimeError(f"Audio file too large ({size_mb:.0f}MB). Split it first.")

    # Lazy import — mlx-whisper is Apple Silicon only
    import mlx_whisper

    try:
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=WHISPER_MODEL_PATH,
            condition_on_previous_text=False,
            hallucination_silence_threshold=5.0,
        )
    except RuntimeError as e:
        if "Failed to load audio" in str(e):
            raise RuntimeError(f"Cannot decode audio: {e}") from e
        raise

    text = result.get("text", "").strip()
    if not text:
        raise RuntimeError("No speech detected in audio")

    # Log segment quality warnings
    for seg in result.get("segments", []):
        if seg.get("compression_ratio", 0) > 2.4:
            print(f"  ⚠️  Segment [{seg['start']:.1f}s-{seg['end']:.1f}s]: high compression — may be repetitive")
        if seg.get("avg_logprob", 0) < -1.0:
            print(f"  ⚠️  Segment [{seg['start']:.1f}s-{seg['end']:.1f}s]: low confidence")
        if seg.get("no_speech_prob", 0) > 0.6:
            print(f"  ⚠️  Segment [{seg['start']:.1f}s-{seg['end']:.1f}s]: likely silence")

    return text
