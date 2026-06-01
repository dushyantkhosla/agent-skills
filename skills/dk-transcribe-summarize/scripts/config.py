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
