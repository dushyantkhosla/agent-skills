"""Configuration constants for the transcribe-av-to-pdf pipeline."""

import os

# OpenRouter transcription model (must support audio_url content type)
MODEL_NAME = "xiaomi/mimo-v2.5"

# Local summarization model via LM Studio
LOCAL_MODEL_NAME = os.environ.get("LOCAL_MODEL_NAME", "gemma-4-e4b-it")

# LM Studio API endpoint
LMSTUDIO_URL = "http://localhost:1234/v1"

# Base output directory
OUTPUT_BASE = "/Users/dush/Code/transcribed"


# ── Fallback model chain (OpenRouter model IDs) ───────────────────
FALLBACK_MODELS = {
    "mimo":               "xiaomi/mimo-v2.5",
    "gemini_flash_lite":  "google/gemini-2.5-flash-lite",
    "gemini_flash":       "google/gemini-2.5-flash",
}

# ── Subtitle quality thresholds ───────────────────────────────────
SUBTITLE_MIN_WPM = 50
SUBTITLE_MIN_WORDS_LONG_VIDEO = 500
SUBTITLE_LONG_VIDEO_THRESHOLD_SECS = 600
SUBTITLE_REPEATED_PHRASE_THRESHOLD = 3

# ── Input validation ──────────────────────────────────────────────
MAX_PROMPT_LENGTH = 2000  # chars

# ── Local whisper (Apple Silicon only, macOS) ────────────────────
WHISPER_MODEL_PATH = "/Users/dush/.lmstudio/models/mlx-community/whisper-large-v3-turbo"
