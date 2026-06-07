# Spec: Smart Hybrid Transcription for dk-transcribe-summarize

**Date:** 2026-06-07
**Status:** Approved
**Author:** Dush + AI (grilled)

---

## Problem Statement

The current `dk-transcribe-summarize` skill only supports audio transcription via OpenRouter's MiMo model. This approach:
- Fails on long videos (>60 min) due to API payload limits
- Incurs API costs for every transcription
- Is slow (download → compress → upload → transcribe)
- Has no fallback when the model fails

A 1h43m podcast episode failed today because MiMo couldn't process the large audio payload, despite working reliably for shorter videos.

---

## Solution: Smart Hybrid Transcription

Implement a multi-stage transcription pipeline that:
1. Tries free, fast subtitle download first
2. Falls back to audio transcription with an OpenRouter model chain
3. As a final fallback, runs mlx-whisper (large-v3-turbo) locally on Apple Silicon — zero cost, fully offline

The script exits with a clear error only after all 5 stages are exhausted.

---

## Transcription Chain

```
┌────────────────────────────────────────────────────────────────┐
│  1. Subtitles (yt-dlp --write-auto-sub)                       │
│     ↓ FAIL / bad quality                                       │
│  2. MiMo (xiaomi/mimo-v2.5) — cheapest API                    │
│     ↓ FAIL                                                     │
│  3. Gemini Flash Lite (google/gemini-2.5-flash-lite) — mid    │
│     ↓ FAIL                                                     │
│  4. Gemini Flash (google/gemini-2.5-flash) — more capable     │
│     ↓ FAIL                                                     │
│  5. mlx-whisper (local, large-v3-turbo) — zero cost, offline  │
│     ↓ FAIL                                                     │
│  ❌ Exit with clear error message                              │
└────────────────────────────────────────────────────────────────┘
```

---

## Failure Conditions

A model is considered "failed" if ANY of these occur:
- HTTP error (400, 429, 500, etc.)
- Empty response
- Response contains a model-refusal pattern (see `is_failure_response` below)
- Timeout (>300 seconds, matching the existing `openrouter_chat` timeout)

Retry policy: **1 initial attempt + 1 retry per model**, then move to next. No backoff needed since we're advancing through a model chain.

### Prerequisite refactoring: `openrouter_chat` must accept a model override

The current `openrouter_chat(messages, max_tokens, temperature)` in `llm.py` hardcodes `"model": MODEL_NAME` in the request body. Before the fallback chain can work, this function must accept an optional `model` parameter:

```python
def openrouter_chat(
    messages: list,
    max_tokens: int = 4000,
    temperature: float = 0,
    model: str | None = None,
) -> str:
    ...
    body = {
        "model": model or MODEL_NAME,  # allow override
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    ...
```

---

## Subtitle Quality Checks

When subtitles are downloaded, validate before accepting:

```python
def check_subtitle_quality(vtt_path, duration_seconds):
    # Guard against zero-duration (livestreams, corrupted metadata)
    if duration_seconds <= 0:
        return "no_duration"

    word_count = count_words(vtt_path)
    wpm = (word_count / duration_seconds) * 60

    # Check 1: Too sparse (bad auto-captions)
    if wpm < SUBTITLE_MIN_WPM:
        return "sparse"

    # Check 2: Garbled (repeated phrases, encoding issues)
    if has_repeated_phrases(vtt_path, threshold=SUBTITLE_REPEATED_PHRASE_THRESHOLD):
        return "garbled"

    # Check 3: Suspiciously short for video length
    if duration_seconds > SUBTITLE_LONG_VIDEO_THRESHOLD_SECS and word_count < SUBTITLE_MIN_WORDS_LONG_VIDEO:
        return "too_short"

    # Check 4: Wrong language
    if detect_language(vtt_path) != "en":
        return "wrong_language"

    return "good"
```

**Edge cases:**
- `duration_seconds <= 0` (livestreams, corrupted metadata): rejected as `no_duration`, triggers audio fallback.
- Music videos, ASMR, or video essays with long silent stretches may trigger false `sparse` — the `too_short` gate catches cases where speech content is genuinely missing. If a false positive occurs, audio fallback handles it.
- `count_words` strips VTT timestamps, HTML tags, and cue markers before counting.

**Rejection triggers fallback to audio chain.**

---

## CLI Interface

```bash
# Default behavior (smart hybrid, 100/400-word summaries) — interactive URL prompt
uv run transcribe_pdf.py

# Force subtitles only (skip audio fallback; exit with error if unavailable)
uv run transcribe_pdf.py --method subtitles

# Force audio only (skip subtitle attempt)
uv run transcribe_pdf.py --method audio

# Custom structured summary (overrides 100/400-word defaults)
uv run transcribe_pdf.py "https://youtube.com/..." --prompt "Summarize per speaker with challenges, tips, and tools"

# Custom summary with specific method
uv run transcribe_pdf.py "https://youtube.com/..." --prompt "Create a study guide" --method subtitles
```

**Input flow design:**
- The URL is accepted as a **positional CLI argument** OR via the existing interactive `input()` prompt (when no URL arg is provided).
- `--method` and `--prompt` are CLI flags only (no interactive prompts for these).
- `parse_args()` returns `(url_or_none, method, prompt_or_none)`. If `url_or_none` is None, the interactive `prompt_user()` fallback is used.
- This preserves the old interactive-only behavior when run with zero args.

**`--method` options:**
- `hybrid` (default, same as no flag) — Smart hybrid pipeline
- `subtitles` — Subtitles only, exit with error if no English subtitles exist OR quality fails. Error message: `"❌ No usable English subtitles found. Try --method hybrid or --method audio."`
- `audio` — Audio transcription only (old behavior, but with fallback chain applied)

**`--prompt` option:**
- Custom summarization instruction
- **Overrides** default 100/400-word summaries when present
- Limited to 2,000 characters (validated at parse time; longer prompts are rejected with an error)

**`is_youtube_url` update:**
- Currently `text.lower().startswith("http")` — too permissive (matches any URL)
- Updated to check for `youtube.com` or `youtu.be` domains:
  ```python
  def is_youtube_url(text: str) -> bool:
      return bool(re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', text))
  ```

---

## User Feedback

Always show summary line after transcription:

```
✅ Transcribed via subtitles (142 WPM, good quality)
   Duration: 1:43:22 | Words: 14,892

⚠️ Subtitles sparse (48 WPM) → fell back to audio
   Used: Gemini Flash Lite | Duration: 45:12 | Words: 6,234

❌ Transcription failed after 5 attempts:
   1. Subtitles: Not available
   2. MiMo: HTTP 400 - Audio too large
   3. Gemini Flash Lite: Empty response
   4. Gemini Flash: Timeout
   5. mlx-whisper: mlx.core error — model not loaded

   Suggestions:
   - Ensure OPENROUTER_API_KEY is set
   - Try a shorter video
   - Ensure running on Apple Silicon for local whisper fallback
```

---

## Output Behavior

| Scenario | Action |
|----------|--------|
| Default (no --prompt) | Generate 100-word + 400-word summaries → PDF/HTML/MD |
| With --prompt | Generate custom summary → PDF/HTML/MD |
| Transcript empty/failed | **No output files**, exit with error |
| Transcript from subtitles | Include `source: subtitles` + quality WPM in metadata |
| Transcript from audio | Include `source: audio` + model name in metadata |

### Metadata Source Notes

In the Markdown output, the metadata table gains a `Source` row:
```
| **Source** | Subtitles (YouTube auto-captions, 142 WPM) |
```
or
```
| **Source** | Audio transcription via Gemini Flash Lite |
```

### Custom Prompt Examples

```bash
# Speaker-based summary
--prompt "For each speaker, list: challenges, tips, and recommended tools"

# Study guide
--prompt "Create a study guide with key concepts and action items"

# Meeting notes
--prompt "Extract action items, decisions, and open questions"

# Technical deep-dive
--prompt "Summarize all technical concepts, tools, and architectures mentioned"
```

---

## File Changes

| File | Changes |
|------|---------|
| `scripts/audio.py` | Add `get_subtitles()`, `check_subtitle_quality()`, `parse_vtt()`, `count_words()`, `has_repeated_phrases()`, `detect_language()` |
| `scripts/llm.py` | **Refactor** `openrouter_chat()` to accept optional `model` param. Add `transcribe_with_fallback()`, `transcribe_with_openrouter()`, `summarize_custom()`, `is_failure_response()`. Extract `FALLBACK_MODELS` list. |
| `scripts/transcribe_pdf.py` | Add `--method` and `--prompt` args, new orchestration logic, `parse_args()`, subtitle tempdir cleanup, prompt length validation |
| `scripts/config.py` | Add `FALLBACK_MODELS` dict, `SUBTITLE_QUALITY` thresholds, `MAX_PROMPT_LENGTH` |
| `scripts/output.py` | Add transcript source to metadata, support custom summary output (`write_custom_output`) |
| `scripts/utils.py` | Update `is_youtube_url()` to check actual YouTube domains |

---

## Library Choices for New Helpers

| Function | Library / approach |
|----------|-------------------|
| `parse_vtt(path)` | `webvtt-py` (pip, lightweight) — parses VTT into cue objects; extract `.text`, join with spaces |
| `count_words(path)` | Regex-strip `[\d:,\.\-\->\s]+` (timestamps), `<[^>]+>` (HTML tags), then `len(result.split())` |
| `has_repeated_phrases(path, threshold)` | Extract all cue texts via `webvtt-py`, sliding window of 5-word n-grams; flag if any n-gram appears ≥ `threshold` times |
| `detect_language(path)` | `langdetect` (pip, lightweight) — feed joined cue text; returns ISO 639-1 code |
| `get_video_duration(url)` | `yt_dlp.YoutubeDL().extract_info(url, download=False).get("duration", 0)` |

Both `webvtt-py` and `langdetect` are added to the script's PEP 723 inline metadata:
```
dependencies = [
    "requests>=2.32",
    "yt-dlp",
    "fpdf2>=2.8",
    "mistune>=3",
    "webvtt-py>=0.5",
    "langdetect>=1.0",
]
```

---

## Implementation Details

### New Function: `get_subtitles(url)`

Fixed to avoid double-download: use a single `extract_info(url, downloads=True)` call.

```python
def get_subtitles(url: str) -> tuple[Path | None, Path | None, str]:
    """Download auto-generated subtitles via yt-dlp.

    Returns (vtt_path, tempdir, language) where:
    - vtt_path is the .en.vtt file (or None)
    - tempdir is the download directory (caller must clean up)
    - language is the detected language code (or "")

    Returns (None, None, "") if no subtitles available or download fails.
    """
    tempdir = Path(tempfile.mkdtemp(prefix="yt_subs_"))

    ydl_opts = {
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "skip_download": True,
        "outtmpl": str(tempdir / "%(id)s.%(ext)s"),
        "quiet": True,
        "cookiesfrombrowser": ("brave",),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None, tempdir, ""

            subs = info.get("subtitles", {})
            auto_subs = info.get("automatic_captions", {})

            if "en" not in subs and "en" not in auto_subs:
                return None, tempdir, ""

        vtt_files = list(tempdir.glob("*.en.vtt"))
        if vtt_files:
            return vtt_files[0], tempdir, "en"
        return None, tempdir, ""
    except Exception:
        return None, tempdir, ""
```

### New Function: `transcribe_with_openrouter(audio_path, model_id)`

Thin wrapper that reuses the existing multimodal message format + compression logic, with a model override:

```python
def transcribe_with_openrouter(audio_path: Path, model_id: str) -> str:
    """Transcribe audio via OpenRouter with a specific model."""
    raw_size = audio_path.stat().st_size
    if raw_size * 4 // 3 > 6_000_000:
        print(f"  Audio is large; compressing for {model_id}...")
        audio_path = compress_audio_for_api(audio_path)

    data_uri = audio_to_data_uri(audio_path)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "audio_url", "audio_url": {"url": data_uri}},
                {
                    "type": "text",
                    "text": "Transcribe this audio. Output only the transcription, no commentary.",
                },
            ],
        }
    ]
    return openrouter_chat(
        messages,
        max_tokens=10000,
        model=model_id,
    )
```

### New Function: `transcribe_with_fallback(audio_path)`

```python
class TranscriptionFailed(Exception):
    """Raised when all transcription models are exhausted."""
    def __init__(self, failures: list[tuple[str, str]]):
        self.failures = failures
        super().__init__(self._format())

    def _format(self) -> str:
        lines = ["Transcription failed after exhausting all models:"]
        for i, (name, reason) in enumerate(self.failures, 1):
            lines.append(f"  {i}. {name}: {reason}")
        return "\n".join(lines)


def transcribe_with_fallback(audio_path: Path) -> tuple[str, str]:
    """Try OpenRouter transcription models in order until success.

    Returns (transcript, model_name).
    Raises TranscriptionFailed if all models are exhausted.
    """
    models = [
        ("MiMo",               FALLBACK_MODELS["mimo"]),
        ("Gemini Flash Lite",  FALLBACK_MODELS["gemini_flash_lite"]),
        ("Gemini Flash",       FALLBACK_MODELS["gemini_flash"]),
    ]

    failures: list[tuple[str, str]] = []

    for name, model_id in models:
        for attempt in range(2):  # 1 initial attempt + 1 retry
            try:
                result = transcribe_with_openrouter(audio_path, model_id)
                if result and not is_failure_response(result):
                    return result, name
                failures.append((name, f"Attempt {attempt+1}: empty/failure response"))
                break  # bad response, don't retry
            except Exception as e:
                failures.append((name, f"Attempt {attempt+1}: {e}"))

    raise TranscriptionFailed(failures)
```

### New Helper: `is_failure_response(text)`

Word-boundary patterns to avoid false-positives on legitimate transcript content:

```python
def is_failure_response(text: str) -> bool:
    """Check if transcription output is a model refusal."""
    if not text or not text.strip():
        return True
    failure_patterns = [
        r"\bno audio\b",
        r"\bno speech detected\b",
        r"\bunable to (transcribe|process)\b",
        r"\bcannot (transcribe|process)\b",
    ]
    t = text.lower()
    return any(re.search(p, t) for p in failure_patterns)
```

Note: the `i don't see any audio` pattern is removed — it's too likely to appear in legitimate conversation transcripts. The remaining patterns use `\b` word boundaries and are restricted to model-refusal phrasing.

### New Function: `summarize_custom(transcript, prompt)`

Routed through `verify_summary` for CoT detection + retry, matching the existing 100/400-word pipeline:

```python
def summarize_custom(transcript: str, prompt: str) -> str:
    """Generate summary based on custom user prompt via local LLM.

    Uses verify_summary for CoT contamination detection and retry.
    For transcripts longer than ~5,000 words, the local model's context
    window may truncate input. In that case, default to the existing
    100/400-word summarize path which handles long input differently.
    """
    word_count = len(transcript.split())
    if word_count > 5000:
        print("  ⚠️  Transcript >5,000 words; custom summary may be truncated.")

    full_prompt = (
        f"Based on the following transcript, {prompt}. "
        f"Output only the summary, no commentary.\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )
    result = local_chat(full_prompt, max_tokens=4000)
    return verify_summary(result, "custom", transcript=transcript)
```

### Modified Main Flow

`download_audio` retains its existing 3-tuple return `(audio_path, title, metadata)`. The tempdir is derived from `audio_path.parent`:

```python
def main():
    url, method, custom_prompt = parse_args()
    if url is None:
        url = prompt_user()  # fall back to interactive input
    if not url:
        print("No input provided.", file=sys.stderr)
        sys.exit(1)

    tempdirs: list[Path] = []
    model_loaded = False

    try:
        transcript: str = ""
        source: str = ""
        source_detail: str = ""
        last_used_model: str = ""
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
                audio_path, title, metadata = download_audio(url)
                tempdirs.append(audio_path.parent)
                transcript, last_used_model = transcribe_with_fallback(audio_path)
                source = "audio"
                source_detail = f"via {last_used_model}"
        else:
            # Local file — audio chain only
            audio_path = Path(url)
            title = audio_path.stem
            transcript, last_used_model = transcribe_with_fallback(audio_path)
            source = "audio"
            source_detail = f"via {last_used_model}"

        # Validate we have something
        if not transcript or len(transcript.split()) < 50:
            print("❌ Transcription failed or too short")
            sys.exit(1)

        # STAGE 2: Summarization
        ensure_lmstudio_ready(LOCAL_MODEL_NAME)
        model_loaded = True

        date_str = dt.date.today().isoformat()
        out_dir = Path(OUTPUT_BASE) / date_str
        out_dir.mkdir(parents=True, exist_ok=True)

        channel = metadata.get("channel", "")
        base_name = sanitize_filename(f"{channel}-{title}" if channel else title)

        if custom_prompt:
            summary = summarize_custom(transcript, custom_prompt)
            write_custom_output(title, summary, transcript, out_dir / f"{base_name}", metadata, source, source_detail)
        else:
            summary_100 = verify_summary(summarize(transcript, 100), "100-word", transcript=transcript, words=100)
            summary_400 = verify_summary(summarize(transcript, 400), "400-word", transcript=transcript, words=400)
            write_output(title, summary_100, summary_400, transcript, out_dir / f"{base_name}", metadata, source, source_detail)

    except TranscriptionFailed as e:
        print(f"❌ {e}", file=sys.stderr)
        print("\n   Suggestions:", file=sys.stderr)
        print("   - Ensure OPENROUTER_API_KEY is set", file=sys.stderr)
        print("   - Try a shorter video", file=sys.stderr)
        sys.exit(1)

    finally:
        if model_loaded:
            unload_lmstudio_model(LOCAL_MODEL_NAME)
        for td in tempdirs:
            shutil.rmtree(td, ignore_errors=True)
```

Key fixes from the previous draft:
- `download_audio` uses the existing 3-tuple return; `audio_tempdir` is `audio_path.parent`
- Only one `--method subtitles` error exit in the flow (consolidated)
- `TranscriptionFailed` is caught at the top level with a formatted error
- `model_loaded` tracking added for LM Studio cleanup (regression from current code)
- `out_dir` and `base_name` construction preserved from existing code

### Config additions (`config.py`)

```python
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
```

---

## Testing Plan

1. **Short video with captions** — Should use subtitles
2. **Short video without captions** — Should fall through to MiMo
3. **Long video (90+ min) with captions** — Should use subtitles
4. **Long video without captions** — Should fall through to Gemini Flash
5. **Video with bad captions** (low WPM) — Should detect and fallback
6. **API key missing** — Should fail at MiMo with clear error
7. **All models fail** — Should exit with `TranscriptionFailed` per-model breakdown
8. **Local file input** — Should skip subtitle attempt, use audio chain
9. **Video with non-English subtitles only** — Should fall through to audio
10. **`--method subtitles` with video that has no English subs** — Should exit with error
11. **`--method audio` flag** — Should skip subtitle attempt, use fallback chain
12. **`--prompt "Extract action items"`** — Should produce custom summary instead of 100/400-word
13. **`--prompt` with >2000 chars** — Should reject at parse time
14. **`--prompt` with transcript >5000 words** — Should warn, proceed with possible truncation
15. **Zero-duration video** (livestream, corrupted) — Should reject subtitle quality as `no_duration`
16. **No CLI args (interactive fallback)** — Should prompt for URL via `input()`

---

## Success Criteria

- [ ] Subtitles attempted first for YouTube URLs
- [ ] Quality checks reject bad captions (including zero/negative duration)
- [ ] Fallback chain works through all 5 stages
- [ ] `openrouter_chat` accepts optional `model` parameter
- [ ] Clear error message when all fail, including per-model failure details
- [ ] No output files generated on failure
- [ ] Summary line shows source + quality info
- [ ] `--method` flag works for all 3 modes (`hybrid`, `subtitles`, `audio`)
- [ ] `--method subtitles` exits with clear error when no English subs available
- [ ] Existing behavior preserved for `--method audio`
- [ ] `--prompt` flag overrides default 100/400-word summaries
- [ ] Custom summaries routed through `verify_summary` (CoT detection + retry)
- [ ] `--prompt` >2,000 chars rejected at parse time
- [ ] `is_youtube_url` rejects non-YouTube URLs
- [ ] All tempdirs cleaned up on both success and failure
- [ ] Interactive `input()` fallback works when no CLI URL arg provided

---

## Out of Scope

- Non-Apple Silicon local transcription (Intel Mac/Linux/Windows need alternative STT)
- Speaker diarization (separate feature)
- Real-time transcription
- Support for non-English languages (future)
- Caching of transcripts (future)
- Chunking for long transcripts in custom summaries (default 100/400-word summaries recommended for long content)
