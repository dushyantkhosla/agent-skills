---
name: dk-transcribe-summarize
description: >
  Transcribe audio files or YouTube videos via subtitles or OpenRouter's
  multimodal API, generate 100-word and 400-word summaries using cloud
  models (OpenRouter) with local LLM fallback (LM Studio), and output
  the results as PDF, HTML, and Markdown files. Supports hybrid
  subtitle-first transcription, custom prompts, and automatic fallback
  across multiple models.
  Triggers on speech-to-text, audio transcription, YouTube download,
  or creating transcript documents with summaries.
license: MIT
compatibility: >
  Requires: ffmpeg, uv, Node.js (for yt-dlp JS challenge solving),
  Brave browser with YouTube login cookies,
  LM Studio (lms CLI) with a loaded model (fallback summarization only),
  OPENROUTER_API_KEY env var for transcription and cloud summarization.
  Python deps (auto-resolved by uv): requests, yt-dlp, fpdf2, mistune,
  webvtt-py, langdetect, mlx-whisper.
metadata:
  author: dushyantkhosla
  model-default: gemma-4-e4b-it
  output-dir: /Users/dush/Code/transcribed/<YYYY-MM-DD>/
  formats: pdf, html, md
---

# Audio Transcribe & Summarize (PDF, HTML & Markdown)

## Overview

Modular Python CLI tool (`scripts/`) that:

1. For YouTube URLs, **tries subtitles first** (hybrid mode) — downloads auto-captions, validates quality (WPM, repeated phrases, language detection), and uses them if good; falls back to audio transcription otherwise
2. Downloads audio from YouTube (or accepts a local mp3/m4a/wav file) when subtitles unavailable or `--method audio`
3. Transcribes audio via **OpenRouter's multimodal API** (`xiaomi/mimo-v2.5`) using the `input_audio` content type
4. Automatically **chunks long audio** (>10 min) into 10-min segments compressed to 16 kbps mono MP3 for reliable cloud transcription
5. Falls back through transcription models (MiMo → Gemini Flash Lite → Gemini Flash → mlx-whisper local), each with 1 retry (each attempt has 5 internal retries with linear backoff)
6. Generates **~100-word and ~400-word summaries** — cloud-first via OpenRouter (same model cascade), falling back to **local LLM via LM Studio** (default: `gemma-4-e4b-it`) only if all cloud models fail or API key is unset
7. Supports **custom prompts** (`--prompt`) for single-summary mode (action items, key takeaways, etc.)
8. Verifies summaries are free of chain-of-thought contamination; retries with a strict prompt if detected
9. Writes three formats — **PDF**, **HTML**, and **Markdown** — to `transcribed/<YYYY-MM-DD>/`. PDF and HTML contain summaries only; **Markdown includes the full transcript**
10. Output filenames use `{channel}-{title}` format when channel metadata is available

## When to Use

- Transcribing audio files (mp3, m4a, wav) to text
- Downloading and transcribing YouTube videos
- Generating summary documents from audio content
- Creating PDF/HTML/Markdown reports with transcripts and summaries
- Working offline for summarization (local LLM, no API cost)

**Do NOT use for:**
- Real-time transcription (batch/offline only)
- Videos longer than ~2 hours (API payload limits)
- Speaker diarization (no speaker labels)

## Quick Reference

| Step | Command |
|------|---------|
| Run (default) | `cd scripts && uv run transcribe_pdf.py` |
| Run with URL | `cd scripts && uv run transcribe_pdf.py "https://youtube.com/..."` |
| Subtitles only | `cd scripts && uv run transcribe_pdf.py --method subtitles` |
| Audio only | `cd scripts && uv run transcribe_pdf.py --method audio` |
| Custom prompt | `cd scripts && uv run transcribe_pdf.py "..." --prompt "Extract action items"` |
| Input | Paste local path or YouTube URL at prompt (if no CLI arg) |
| Output | `transcribed/<YYYY-MM-DD>/<channel>-<title>.{pdf,html,md}` |
| API key | `OPENROUTER_API_KEY` env var (for transcription and cloud summarization) |
| Local model | Override with `LOCAL_MODEL_NAME` env var (default: `gemma-4-e4b-it`) |
| Prerequisites | `ffmpeg`, `uv`, `lms` (LM Studio CLI), Node.js |

## Script

Reusable tool: `scripts/transcribe_pdf.py`

```bash
cd /path/to/skill
uv run scripts/transcribe_pdf.py
```

## Coding Standards

### All Python scripts MUST use PEP 723 inline metadata

Every executable Python script in this skill must:

- Start with `#!/usr/bin/env -S uv run --script` shebang
- Include a `# /// script` block with `requires-python` and `dependencies` list
- Be runnable via `uv run <script.py>` without any pre-existing virtual environment

This ensures zero configuration — `uv` creates an isolated environment automatically.

```python
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
```

Non-executable modules (imported by scripts) do not need the shebang or script block.

**Dependencies** (PEP 723 inline metadata in `transcribe_pdf.py`):
- `requests>=2.32` — HTTP client for OpenRouter and LM Studio APIs
- `yt-dlp` — YouTube audio download and subtitle extraction
- `fpdf2>=2.8` — PDF generation
- `mistune>=3` — Markdown-to-HTML conversion for HTML output
- `webvtt-py>=0.5` — VTT subtitle parsing
- `langdetect>=1.0` — Language detection for subtitle quality checks
- `mlx-whisper>=0.4` — Local transcription fallback (Apple Silicon only)

## How It Works

### Phase 1: Input & Validation

1. **validate_environment()** — checks `OPENROUTER_API_KEY`, `ffmpeg`, `uv`, and `lms` are available
2. **parse_args()** or **prompt_user()** — accepts URL/file path, `--method` (hybrid/subtitles/audio), and optional `--prompt`

### Phase 2: Transcription (Hybrid Pipeline)

For YouTube URLs with `--method hybrid` (default) or `--method subtitles`:

3. **get_subtitles()** — downloads auto-generated English subtitles via `yt-dlp` (VTT format)
4. **check_subtitle_quality()** — validates subtitle quality:
   - Word-per-minute rate (min 50 WPM)
   - Repeated phrase detection (flags garbled captions)
   - Language detection (must be English)
   - Minimum word count for long videos (500+ words for >10min)
5. If quality is "good" → **parse_vtt()** extracts text, skip to Phase 3
6. If quality is poor or subtitles unavailable → fall through to audio transcription

For `--method audio` or when subtitles fail:

7. **download_audio()** — downloads best audio via `yt-dlp` with:
   - Brave browser cookies (for YouTube auth)
   - JS runtime (Node.js) + EJS remote component (for n-challenge solving)
   - FFmpeg post-processing to .m4a
8. **transcribe_with_fallback()** — tries models in order, each with 1 retry (each attempt has 5 internal retries with linear backoff):
   - MiMo (`xiaomi/mimo-v2.5`) — cheapest, default
   - Gemini Flash Lite (`google/gemini-2.5-flash-lite`) — mid-tier
   - Gemini Flash (`google/gemini-2.5-flash`) — most capable
   - mlx-whisper (local, Apple Silicon) — zero cost, offline
   - Audio >10 min is auto-chunked into 10-min segments (16 kbps mono MP3)
   - If all models fail → raises `TranscriptionFailed` with detailed error

### Phase 3: Summarization (Cloud-First)

9. **summarize()** → **summarize_with_fallback()** — generates summaries (cloud-first, local fallback):
   - Tries OpenRouter models in order: MiMo → Gemini Flash Lite → Gemini Flash
   - Each model has 1 retry with 5 internal retries per attempt
   - If all cloud models fail or `OPENROUTER_API_KEY` is unset → falls back to LM Studio
   - **ensure_lmstudio_ready()** — starts LM Studio server if needed, loads model (`gemma-4-e4b-it`)
   - **local_chat()** — calls LM Studio's OpenAI-compatible API
   - Special handling: Qwen models get `enable_thinking: false` to reduce CoT contamination
10. **verify_summary()** — checks each summary for CoT contamination:
    - Scans for trigger phrases: `thinking process`, `analyze the`, `drafting`, `iterative`, `step-by-step`, `let me think`, `here's my reasoning`
    - If detected → retries with strict prompt ("Output ONLY the summary text. No preamble, no analysis...")
    - If still contaminated → strips `<thinking>`, `<reasoning>` XML tags and numbered analysis lists via `_strip_thinking()`

### Phase 4: Output & Cleanup

1. **write_pdf()**, **write_html()**, **write_markdown()** — writes three formats to `transcribed/<YYYY-MM-DD>/`:
   - Filename: `{channel}-{title}.{ext}` (or just `{title}.{ext}` if no channel)
   - PDF and HTML: title page + 100-word summary + 400-word summary (no transcript)
   - Markdown: metadata table + source info + summaries + **full transcript**
2. For custom prompts (`--prompt`):
   - **summarize_custom()** — generates single summary with custom instruction
   - **write_custom_output()** — writes PDF/HTML/Markdown with single summary section
   - Warns if transcript >5000 words (context window risk)
3. **Cleanup** — **unload_lmstudio_model()** frees GPU memory, removes temp directories

## Verification

After each summary is generated, `verify_summary()` runs a three-stage pipeline:

1. **Check** — scans for CoT trigger phrases: `thinking process`, `analyze the`, `drafting`, `iterative`, `step-by-step`, `let me think`, `here's my reasoning`
2. **Retry** — if contamination detected, re-generates with a strict prompt: *"Output ONLY the summary text. No preamble, no analysis, no thinking, no numbered steps, no meta-commentary."*
3. **Strip** — if retry is still contaminated, runs `_strip_thinking()` as a safety net:
   - Removes `<thinking>...</thinking>` and `<reasoning>...</reasoning>` XML blocks
   - Removes `Thinking:` / `Reasoning:` / `Thought:` line headers
   - Removes numbered analysis list items (`1.`, `2.`, etc.)

## External Dependencies

The script is **not** fully self-contained. Here is every external dependency:

### Runtime & CLI Tools
| Dependency | Why | Install |
|------------|-----|---------|
| `uv` | Runs the Python script (PEP 723 inline metadata) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `ffmpeg` | Audio compression + yt-dlp post-processing | `brew install ffmpeg` / `apt install ffmpeg` |
| `lms` (LM Studio CLI) | Start/stop/load/unload local LLM | Download LM Studio from https://lmstudio.ai |
| `node` | JavaScript runtime for yt-dlp n-challenge solving (already installed) | Pre-installed via nvm |

### Python Packages (auto-resolved by `uv run --script`)
| Package | Version | Used For |
|---------|---------|----------|
| `requests` | ≥2.32 | HTTP client for OpenRouter + LM Studio APIs |
| `yt-dlp` | latest | YouTube audio download, subtitle extraction, cookie/JS support |
| `mistune` | ≥3.0 | Markdown-to-HTML conversion for the HTML output file |
| `fpdf2` | ≥2.8 | PDF generation |
| `webvtt-py` | ≥0.5 | VTT subtitle parsing |
| `langdetect` | ≥1.0 | Language detection for subtitle quality checks |
| `mlx-whisper` | ≥0.4 | Local transcription fallback (Apple Silicon only) |

### Environment Variables
| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | ✅ Yes | Authentication for OpenRouter transcription and cloud summarization APIs |
| `LOCAL_MODEL_NAME` | ❌ Optional | Override default summarization model (default: `gemma-4-e4b-it`) |

### Running Services
| Service | Port | Why |
|---------|------|-----|
| LM Studio server | `localhost:1234` | Serves the local LLM via OpenAI-compatible API |
| Brave browser (with YouTube cookies) | N/A | Provides authenticated YouTube session for yt-dlp |

### Network Access
| Endpoint | Purpose |
|----------|---------|
| `https://openrouter.ai/api/v1/chat/completions` | Audio transcription + cloud summarization (MiMo, Gemini Flash Lite/Flash) |
| `https://www.youtube.com` | Video page + audio download |
| `https://github.com/yt-dlp/ejs/releases/...` | EJS challenge solver script (auto-downloaded) |
| `http://localhost:1234/v1/chat/completions` | Local summarization via LM Studio |

### File System
| Path | Purpose |
|------|---------|
| `/Users/dush/Code/transcribed/<YYYY-MM-DD>/` | Output directory for PDF, HTML, Markdown (auto-created) |
| Temporary directories | yt-dlp download cache, compressed audio (cleaned up) |

> **Note:** The only dependencies `uv` resolves automatically are the seven Python packages listed above. Everything else — system tools, running services, browser cookies, API keys — must be present on the machine before running.

## Configuration

| Setting | Default | Notes |
|---------|---------|-------|
| Transcription model | `xiaomi/mimo-v2.5` | On OpenRouter. Change `MODEL_NAME` in `config.py` |
| Local summarization model | `gemma-4-e4b-it` | Override via `LOCAL_MODEL_NAME` env var |
| LM Studio URL | `http://localhost:1234/v1` | Change `LMSTUDIO_URL` in `config.py` |
| Audio compression (single file) | 8 kbps mono MP3 | 16 kHz sample rate, compressed via ffmpeg |
| Audio compression (chunks) | 16 kbps mono MP3 | 10-min chunks for cloud API |
| Max chunk duration | 600s (10 min) | Change `MAX_CHUNK_SECONDS` in `config.py` |
| Max tokens (transcription) | 10,000 | Covers ~60-90 min of speech per chunk |
| Output directory | `/Users/dush/Code/transcribed/<YYYY-MM-DD>/` | Change `OUTPUT_BASE` in `config.py` |
| Transcription fallback | MiMo → Gemini Flash Lite → Gemini Flash → mlx-whisper | Change `FALLBACK_MODELS` in `config.py` |
| Summarization fallback | MiMo → Gemini Flash Lite → Gemini Flash → LM Studio | Change `SUMMARIZATION_MODELS` in `config.py` |
| Whisper model path | `~/.lmstudio/models/mlx-community/whisper-large-v3-turbo` | Change `WHISPER_MODEL_PATH` in `config.py` |
| Subtitle min WPM | 50 | Change `SUBTITLE_MIN_WPM` in `config.py` |
| Max prompt length | 2000 chars | Change `MAX_PROMPT_LENGTH` in `config.py` |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `OPENROUTER_API_KEY` not set | Export it in your shell env |
| `ffmpeg` not found | `brew install ffmpeg` or `apt install ffmpeg` |
| `lms` not found | Install LM Studio from https://lmstudio.ai |
| 400 error "exceeds 8 MB" | Video too long; auto-chunking splits into 10-min segments |
| yt-dlp JS runtime warning | Install Deno: `brew install deno` |
| Empty transcription | Check audio isn't silent or corrupted |
| Summary has thinking noise | Script auto-detects, retries with strict prompt, then strips; try a different model via `LOCAL_MODEL_NAME` |
| whisper fails / not found | mlx-whisper requires Apple Silicon. If on Intel/Linux, the script exits after cloud models with a clear error. |
| Subtitles garbled or sparse | Quality checks catch WPM <50, repeated phrases, wrong language. Use `--method audio` to skip subtitles. |
| Custom summary truncated | Transcript >5000 words may exceed local model context. Use default 100/400-word pipeline for long content. |
