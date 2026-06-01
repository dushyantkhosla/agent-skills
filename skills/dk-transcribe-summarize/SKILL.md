---
name: dk-transcribe-summarize
description: >
  Transcribe audio files or YouTube videos via OpenRouter's multimodal API,
  generate 100-word and 400-word summaries using a local LLM (LM Studio),
  and output the results as PDF, HTML, and Markdown files.
  Triggers on speech-to-text, audio transcription, YouTube download,
  or creating transcript documents with summaries.
license: MIT
compatibility: >
  Requires: ffmpeg, uv, Node.js (for yt-dlp JS challenge solving),
  Brave browser with YouTube login cookies,
  LM Studio (lms CLI) with a loaded model,
  OPENROUTER_API_KEY env var for transcription.
  Python deps (auto-resolved by uv): requests, yt-dlp, fpdf2.
metadata:
  author: dushyantkhosla
  model-default: gemma-4-e4b-it
  output-dir: /Users/dush/Code/transcribed/<YYYY-MM-DD>/
  formats: pdf, html, md
---

# Audio Transcribe & Summarize (PDF, HTML & Markdown)

## Overview

Modular Python CLI tool (`scripts/`) that:

1. Downloads audio from YouTube (or accepts a local mp3/m4a/wav file)
2. Transcribes it via **OpenRouter's multimodal API** (`xiaomi/mimo-v2.5`)
3. Generates **~100-word and ~400-word summaries** using a **local LLM via LM Studio** (default: `gemma-4-e4b-it`)
4. Verifies summaries are free of chain-of-thought contamination
5. Writes all three formats — **PDF**, **HTML**, and **Markdown** — to `transcribed/<YYYY-MM-DD>/`

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
| Run | `cd scripts && uv run transcribe_pdf.py` |
| Input | Paste local path or YouTube URL at prompt |
| Output | `transcribed/<YYYY-MM-DD>/<title>.pdf` + `.html` + `.md` |
| API key | `OPENROUTER_API_KEY` env var (for transcription only) |
| Local model | Override with `LOCAL_MODEL_NAME` env var (default: `gemma-4-e4b-it`) |
| Prerequisites | `ffmpeg`, `uv`, `lms` (LM Studio CLI), Node.js |

## Script

Reusable tool: `scripts/transcribe_pdf.py`

```bash
cd /path/to/skill
uv run scripts/transcribe_pdf.py
```

**Dependencies** (PEP 723 inline metadata in the script):
- `requests>=2.32` — HTTP client for OpenRouter and LM Studio APIs
- `yt-dlp` — YouTube audio download
- `fpdf2>=2.8` — PDF generation

## How It Works

1. **validate_environment()** — checks `OPENROUTER_API_KEY`, `ffmpeg`, `uv`, and `lms` are available
2. **Prompts** for input — local file path or YouTube URL
3. **download_audio()** — downloads best audio via `yt-dlp` with:
   - Brave browser cookies (for YouTube auth)
   - JS runtime (Node.js) + EJS remote component (for n-challenge solving)
   - FFmpeg post-processing to .m4a
4. **transcribe()** — sends audio as base64 data URI to OpenRouter's `xiaomi/mimo-v2.5`; auto-compresses with ffmpeg if >6 MB
5. **ensure_lmstudio_ready()** — starts LM Studio server if needed, loads the local model
6. **summarize()** — generates ~100-word and ~400-word summaries via the local model's OpenAI-compatible API
7. **verify_summary()** — checks each summary for chain-of-thought contamination ("Thinking Process:", "Analyze the:", etc.); strips it if found
8. **write_pdf()**, **write_html()**, **write_markdown()** — writes all three formats to `transcribed/<YYYY-MM-DD>/`
9. **Cleanup** — unloads the LM Studio model, removes temp files

## Verification

After each summary is generated, the script runs `verify_summary()` which:

- Checks for CoT trigger phrases: `thinking process`, `analyze the`, `drafting`, `iterative`, `step-by-step`, `let me think`, `here's my reasoning`
- If contamination is detected, warns with ⚠️ and the output is run through `_strip_thinking()` as a safety net
- The `_strip_thinking()` function removes `<thinking>`, `<reasoning>` XML tags, numbered analysis lists, and "Thinking/Reasoning/Thought:" headers

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
| `yt-dlp` | latest | YouTube audio download with cookie/JS support |
| `mistune` | ≥3.0 | Markdown-to-HTML conversion for the HTML output file |
| `fpdf2` | ≥2.8 | PDF generation |

### Environment Variables
| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | ✅ Yes | Authentication for OpenRouter transcription API |
| `LOCAL_MODEL_NAME` | ❌ Optional | Override default summarization model (default: `gemma-4-e4b-it`) |

### Running Services
| Service | Port | Why |
|---------|------|-----|
| LM Studio server | `localhost:1234` | Serves the local LLM via OpenAI-compatible API |
| Brave browser (with YouTube cookies) | N/A | Provides authenticated YouTube session for yt-dlp |

### Network Access
| Endpoint | Purpose |
|----------|---------|
| `https://openrouter.ai/api/v1/chat/completions` | Audio transcription via `xiaomi/mimo-v2.5` |
| `https://www.youtube.com` | Video page + audio download |
| `https://github.com/yt-dlp/ejs/releases/...` | EJS challenge solver script (auto-downloaded) |
| `http://localhost:1234/v1/chat/completions` | Local summarization via LM Studio |

### File System
| Path | Purpose |
|------|---------|
| `/Users/dush/Code/transcribed/<YYYY-MM-DD>/` | Output directory for PDF, HTML, Markdown (auto-created) |
| Temporary directories | yt-dlp download cache, compressed audio (cleaned up) |

> **Note:** The only dependencies `uv` resolves automatically are the three Python packages. Everything else — system tools, running services, browser cookies, API keys — must be present on the machine before running.

## Configuration

| Setting | Default | Notes |
|---------|---------|-------|
| Transcription model | `xiaomi/mimo-v2.5` | On OpenRouter. Change `MODEL_NAME` in script |
| Local summarization model | `gemma-4-e4b-it` | Override via `LOCAL_MODEL_NAME` env var |
| LM Studio URL | `http://localhost:1234/v1` | Change `LMSTUDIO_URL` in script |
| Audio compression | 8kbps mono MP3 | Triggered when raw audio > ~4.5 MB |
| Max tokens (transcription) | 10,000 | Covers ~60-90 min of speech |
| Output directory | `transcribed/<YYYY-MM-DD>/` | At `/Users/dush/Code/transcribed/<YYYY-MM-DD>/` |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `OPENROUTER_API_KEY` not set | Export it in your shell env |
| `ffmpeg` not found | `brew install ffmpeg` or `apt install ffmpeg` |
| `lms` not found | Install LM Studio from https://lmstudio.ai |
| 400 error "exceeds 8 MB" | Video too long; auto-compression may not be enough |
| yt-dlp JS runtime warning | Install Deno: `brew install deno` |
| Empty transcription | Check audio isn't silent or corrupted |
| Summary has thinking noise | Script auto-detects and strips it; try a different model via `LOCAL_MODEL_NAME` |
