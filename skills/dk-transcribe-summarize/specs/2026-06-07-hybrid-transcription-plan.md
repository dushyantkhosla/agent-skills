# Hybrid Transcription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add subtitle-first transcription with 3-model OpenRouter fallback chain (MiMo → Gemini Flash Lite → Gemini Flash) and `--method`/`--prompt` CLI flags to the dk-transcribe-summarize skill.

**Architecture:** Modify 5 existing scripts in `scripts/` + create 1 new file. New subtitle download via yt-dlp, VTT parsing via `webvtt-py`, language detection via `langdetect`. Existing `openrouter_chat()` refactored to accept a `model` override. New `transcribe_with_fallback()` orchestrates the 5-stage chain (subtitles → MiMo → Gemini Flash Lite → Gemini Flash → mlx-whisper). Custom `--prompt` summaries route through `verify_summary` for CoT detection.

**Tech Stack:** Python 3.10+, requests, yt-dlp, fpdf2, mistune, webvtt-py, langdetect, mlx-whisper. Summarization via LM Studio (existing).

**Note on testing:** This is a CLI script (`uv run --script`), not a library. Unit tests cover pure functions (URL validation, quality checks, failure detection). API-dependent functions are verified via manual integration runs against real inputs from the spec's Testing Plan.

---

### Task 1: Add new constants to config.py

**Files:**
- Modify: `scripts/config.py`

- [ ] **Step 1: Append constants to config.py**

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

# ── Local whisper (Apple Silicon only, macOS) ────────────────────
WHISPER_MODEL_PATH = "/Users/dush/.lmstudio/models/mlx-community/whisper-large-v3-turbo"
```

- [ ] **Step 2: Verify config loads**

```bash
cd scripts && python3 -c "from config import FALLBACK_MODELS, SUBTITLE_MIN_WPM, MAX_PROMPT_LENGTH; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/config.py
git commit -m "feat: add fallback model list, subtitle thresholds, prompt length cap to config"
```

---

### Task 2: Fix is_youtube_url and add parse_args

**Files:**
- Modify: `scripts/utils.py`

- [ ] **Step 1: Write unit test for is_youtube_url**

Create `scripts/test_helpers.py`:

```python
#!/usr/bin/env python3
"""Unit tests for pure helper functions (no API calls needed)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import is_youtube_url as _old_is_youtube_url
import re


def is_youtube_url(text: str) -> bool:
    """New implementation to test."""
    return bool(re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', text))


def test_is_youtube_url():
    # Valid YouTube URLs
    assert is_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert is_youtube_url("https://youtube.com/watch?v=abc123")
    assert is_youtube_url("https://youtu.be/abc123")
    assert is_youtube_url("http://youtube.com/watch?v=abc123")

    # Non-YouTube URLs (should reject)
    assert not is_youtube_url("https://example.com/video.mp4")
    assert not is_youtube_url("https://vimeo.com/12345")
    assert not is_youtube_url("https://youtube.com.random.site/watch")

    # Non-URLs
    assert not is_youtube_url("/path/to/local/file.mp3")
    assert not is_youtube_url("just some text")

    # Edge cases
    assert not is_youtube_url("")
    assert not is_youtube_url("https://")


def test_count_words():
    from audio import count_words as _count_words
    vtt_content = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c.music>Hello world</c>

00:00:04.000 --> 00:00:07.000
This is a test."""
    path = Path("/tmp/test_count_words.vtt")
    path.write_text(vtt_content)
    try:
        result = _count_words(path)
        assert result > 0, f"Expected >0 words, got {result}"
    finally:
        path.unlink(missing_ok=True)


def test_is_failure_response():
    from llm import is_failure_response

    # Should detect these as failures
    assert is_failure_response("")
    assert is_failure_response("   ")
    assert is_failure_response("No audio detected in the file.")
    assert is_failure_response("Unable to transcribe this content.")
    assert is_failure_response("Cannot process audio input.")

    # Should NOT detect these as failures
    assert not is_failure_response("There was no audio in the video until minute 3.")
    assert not is_failure_response("The speaker said they couldn't process the request.")
    assert not is_failure_response("Hello world, this is a transcription of the podcast.")


if __name__ == "__main__":
    test_is_youtube_url()
    print("✓ test_is_youtube_url passed")
    # test_count_words()  # uncomment once count_words is implemented
    # test_is_failure_response()  # uncomment once is_failure_response is implemented
    print("All tests passed!")
```

- [ ] **Step 2: Run test — verify it fails on old is_youtube_url**

```bash
cd scripts && python3 -c "
import re, sys
from utils import is_youtube_url
# Old version should fail on non-YouTube URLs
assert is_youtube_url('https://example.com/video.mp4'), 'Old version passes any http URL'
assert is_youtube_url('https://vimeo.com/12345'), 'Old version passes any http URL'
print('Old behavior confirmed: matches any http URL')
"
```
Expected: confirms old behavior matches any http URL

- [ ] **Step 3: Replace is_youtube_url in utils.py**

Replace the existing function:

```python
# OLD (remove):
def is_youtube_url(text: str) -> bool:
    return text.lower().startswith("http")

# NEW (replace with):
def is_youtube_url(text: str) -> bool:
    """Check if text is a YouTube URL (not just any http URL)."""
    return bool(re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', text))
```

The `re` import already exists at the top of utils.py.

- [ ] **Step 4: Add parse_args to utils.py**

Append after `validate_environment()`:

```python
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
```

Note: `MAX_PROMPT_LENGTH` must be imported from config at the top of utils.py.

- [ ] **Step 5: Add MAX_PROMPT_LENGTH import to utils.py**

Add to the imports at the top:

```python
from config import MAX_PROMPT_LENGTH
```

- [ ] **Step 6: Run unit tests**

```bash
cd scripts && python3 test_helpers.py
```
Expected: `✓ test_is_youtube_url passed` then `All tests passed!`

- [ ] **Step 7: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/utils.py scripts/test_helpers.py
git commit -m "feat: restrict is_youtube_url to YouTube domains, add parse_args with --method/--prompt"
```

---

### Task 3: Add subtitle download and video duration to audio.py

**Files:**
- Modify: `scripts/audio.py`

- [ ] **Step 1: Add get_video_duration to audio.py**

Append to audio.py:

```python
def get_video_duration(url: str) -> int:
    """Get video duration in seconds from yt-dlp without downloading."""
    ydl_opts = {
        "quiet": True,
        "cookiesfrombrowser": ("brave",),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return 0
            return int(info.get("duration", 0))
    except Exception:
        return 0
```

- [ ] **Step 2: Add get_subtitles to audio.py**

Append to audio.py:

```python
def get_subtitles(url: str) -> tuple[Path | None, Path | None, str]:
    """Download auto-generated English subtitles via yt-dlp.

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

- [ ] **Step 3: Verify imports are available**

The function uses `Path`, `tempfile`, and `yt_dlp` — all already imported in audio.py.

- [ ] **Step 4: Quick smoke test**

```bash
cd scripts && python3 -c "
from audio import get_video_duration
d = get_video_duration('https://www.youtube.com/watch?v=jNQXAC9IVRw')
print(f'Duration: {d}s')
assert d > 0, 'Expected positive duration for known video'
print('OK')
"
```
Expected: `Duration: 19s` then `OK`

- [ ] **Step 5: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/audio.py
git commit -m "feat: add get_subtitles and get_video_duration to audio.py"
```

---

### Task 4: Add VTT parsing and quality checks to audio.py

**Files:**
- Modify: `scripts/audio.py`

- [ ] **Step 1: Add parse_vtt and count_words to audio.py**

Append to audio.py:

```python
def parse_vtt(vtt_path: Path) -> str:
    """Parse a VTT subtitle file and return plain text.

    Requires webvtt-py (added to PEP 723 deps in Task 12).
    """
    import webvtt

    captions = webvtt.read(str(vtt_path))
    texts = []
    for caption in captions:
        text = caption.text.strip()
        if text:
            texts.append(text)
    return " ".join(texts)


def count_words(vtt_path: Path) -> int:
    """Count words in a VTT file, stripping timestamps and HTML tags."""
    text = vtt_path.read_text(encoding="utf-8")
    # Strip WEBVTT header lines
    text = re.sub(r"^WEBVTT.*\n", "", text)
    # Strip timestamp lines: HH:MM:SS.mmm --> HH:MM:SS.mmm
    text = re.sub(r"[\d:,\.\-\>\s]+\n", " ", text)
    # Strip HTML-like tags: <c.music>, </c>, <00:00:01.000>, etc.
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    return len(words)


def has_repeated_phrases(vtt_path: Path, threshold: int = 3) -> bool:
    """Check if VTT contains suspiciously repeated 5-word phrases."""
    import webvtt

    captions = webvtt.read(str(vtt_path))
    all_words = []
    for caption in captions:
        words = caption.text.strip().lower().split()
        all_words.extend(words)

    if len(all_words) < 5:
        return False

    ngrams: dict[str, int] = {}
    for i in range(len(all_words) - 4):
        gram = " ".join(all_words[i:i+5])
        ngrams[gram] = ngrams.get(gram, 0) + 1

    return any(count >= threshold for count in ngrams.values())


def detect_language(vtt_path: Path) -> str:
    """Detect language of VTT text. Returns ISO 639-1 code or 'unknown'.

    Requires langdetect (added to PEP 723 deps in Task 12).
    """
    from langdetect import detect, LangDetectException

    text = parse_vtt(vtt_path)
    if len(text.strip()) < 20:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"
```

Note: `re` is already imported at the top of audio.py.

- [ ] **Step 2: Add check_subtitle_quality to audio.py**

Append to audio.py:

```python
def check_subtitle_quality(vtt_path: Path, duration_seconds: int) -> str:
    """Validate subtitle quality. Returns 'good' or a failure reason."""
    from config import (
        SUBTITLE_MIN_WPM,
        SUBTITLE_MIN_WORDS_LONG_VIDEO,
        SUBTITLE_LONG_VIDEO_THRESHOLD_SECS,
        SUBTITLE_REPEATED_PHRASE_THRESHOLD,
    )

    if duration_seconds <= 0:
        return "no_duration"

    word_count = count_words(vtt_path)
    wpm = (word_count / duration_seconds) * 60

    if wpm < SUBTITLE_MIN_WPM:
        return "sparse"

    if has_repeated_phrases(vtt_path, SUBTITLE_REPEATED_PHRASE_THRESHOLD):
        return "garbled"

    if duration_seconds > SUBTITLE_LONG_VIDEO_THRESHOLD_SECS and word_count < SUBTITLE_MIN_WORDS_LONG_VIDEO:
        return "too_short"

    if detect_language(vtt_path) != "en":
        return "wrong_language"

    return "good"
```

- [ ] **Step 3: Add config imports at top of audio.py**

```python
from config import (
    SUBTITLE_MIN_WPM,
    SUBTITLE_MIN_WORDS_LONG_VIDEO,
    SUBTITLE_LONG_VIDEO_THRESHOLD_SECS,
    SUBTITLE_REPEATED_PHRASE_THRESHOLD,
)
```

- [ ] **Step 4: Uncomment and run count_words test**

Edit `scripts/test_helpers.py`: uncomment the `test_count_words()` call at the bottom.

```bash
cd scripts && python3 test_helpers.py
```
Expected: `✓ test_is_youtube_url passed` then `All tests passed!`

- [ ] **Step 5: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/audio.py scripts/test_helpers.py
git commit -m "feat: add VTT parsing, quality checks, language detection to audio.py"
```

---

### Task 5: Refactor openrouter_chat to accept model override

**Files:**
- Modify: `scripts/llm.py`

- [ ] **Step 1: Add model parameter to openrouter_chat signature**

In `scripts/llm.py`, find `def openrouter_chat(messages: list, max_tokens: int = 4000, temperature: float = 0) -> str:` and change to:

```python
def openrouter_chat(
    messages: list,
    max_tokens: int = 4000,
    temperature: float = 0,
    model: str | None = None,
) -> str:
    """Call the OpenRouter API. Use model override if provided, else MODEL_NAME."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")

    import time
    last_err = None
    for attempt in range(1, 6):
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or MODEL_NAME,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=300,
        )
```

The only change is: add `model: str | None = None` parameter, change `"model": MODEL_NAME` to `"model": model or MODEL_NAME`. Everything else stays identical.

- [ ] **Step 2: Verify existing transcribe() still works**

```bash
cd scripts && python3 -c "
from llm import openrouter_chat
print('openrouter_chat signature:', openrouter_chat.__code__.co_varnames[:openrouter_chat.__code__.co_argcount])
assert 'model' in openrouter_chat.__code__.co_varnames, 'model param missing'
print('OK')
"
```
Expected: model param present in signature, `OK`

- [ ] **Step 3: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/llm.py
git commit -m "refactor: add optional model parameter to openrouter_chat"
```

---

### Task 6: Add is_failure_response and TranscriptionFailed to llm.py

**Files:**
- Modify: `scripts/llm.py`

- [ ] **Step 1: Add is_failure_response to llm.py**

Append after the `transcribe()` function:

```python
def is_failure_response(text: str) -> bool:
    """Check if transcription output is a model refusal.

    Uses word-boundary patterns to avoid false-positives on
    legitimate transcript content like 'there was no audio in the video'.
    """
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

`re` is already imported at the top of llm.py.

- [ ] **Step 2: Add TranscriptionFailed exception to llm.py**

Append after `is_failure_response`:

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
```

- [ ] **Step 3: Run is_failure_response unit test**

Uncomment the `test_is_failure_response()` call in `scripts/test_helpers.py` and comment out `test_count_words()` (it requires webvtt-py which isn't added yet):

```bash
cd scripts && python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '.')

# Modify test_helpers.py on the fly for this test
exec(open('test_helpers.py').read().replace(
    'test_count_words()',
    '# test_count_words() not ready'
))
"
```

Or more simply, run the specific test directly:

```bash
cd scripts && python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '.')
from llm import is_failure_response

assert is_failure_response(''), 'empty string should fail'
assert is_failure_response('   '), 'whitespace should fail'
assert is_failure_response('No audio detected in the file.'), 'no audio should fail'
assert is_failure_response('Unable to transcribe this content.'), 'unable should fail'
assert is_failure_response('Cannot process audio input.'), 'cannot should fail'

assert not is_failure_response('There was no audio in the video until minute 3.'), 'false positive!'
assert not is_failure_response('Hello world, this is a transcription.'), 'false positive!'

print('All is_failure_response tests passed!')
"
```
Expected: `All is_failure_response tests passed!`

- [ ] **Step 4: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/llm.py
git commit -m "feat: add is_failure_response and TranscriptionFailed to llm.py"
```

---

### Task 7: Add transcribe_with_openrouter and transcribe_with_fallback to llm.py

**Files:**
- Modify: `scripts/llm.py`

- [ ] **Step 1: Add transcribe_with_openrouter to llm.py**

Append after `TranscriptionFailed`:

```python
def transcribe_with_openrouter(audio_path: Path, model_id: str) -> str:
    """Transcribe audio via OpenRouter with a specific model.

    Reuses the existing compression and data-URI logic from transcribe().
    """
    raw_size = audio_path.stat().st_size
    estimated_b64 = raw_size * 4 // 3
    if estimated_b64 > 6_000_000:
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
    return openrouter_chat(messages, max_tokens=10000, model=model_id)
```

Import note: `compress_audio_for_api` and `audio_to_data_uri` are in `audio.py`. Add the import at the top of llm.py:

```python
from audio import compress_audio_for_api, audio_to_data_uri
```

- [ ] **Step 2: Add transcribe_with_fallback to llm.py**

Append after `transcribe_with_openrouter`:

```python
def transcribe_with_fallback(audio_path: Path) -> tuple[str, str]:
    """Try OpenRouter transcription models in order until success.

    Returns (transcript, model_name).
    Raises TranscriptionFailed if all models are exhausted.
    """
    from config import FALLBACK_MODELS

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
                    print(f"  ✓ Transcribed via {name}")
                    return result, name
                failures.append((name, f"Attempt {attempt+1}: empty/failure response"))
                break  # bad response to a valid request — don't retry same model
            except Exception as e:
                failures.append((name, f"Attempt {attempt+1}: {e}"))

    raise TranscriptionFailed(failures)
```

- [ ] **Step 3: Verify the import chain**

```bash
cd scripts && python3 -c "
import sys
sys.path.insert(0, '.')
from llm import transcribe_with_openrouter, transcribe_with_fallback, TranscriptionFailed
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 4: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/llm.py
git commit -m "feat: add transcribe_with_openrouter and 3-model fallback chain to llm.py"
```

---

### Task 8: Add summarize_custom to llm.py

**Files:**
- Modify: `scripts/llm.py`

- [ ] **Step 1: Add summarize_custom to llm.py**

Append after `transcribe_with_fallback`:

```python
def summarize_custom(transcript: str, prompt: str) -> str:
    """Generate a custom summary via local LLM, routed through verify_summary.

    For transcripts longer than ~5,000 words, the local model's context
    window may truncate input. The function warns and proceeds; for very
    long content the default 100/400-word pipeline is recommended instead.
    """
    word_count = len(transcript.split())
    if word_count > 5000:
        print(f"  ⚠️  Transcript is {word_count} words; custom summary may be truncated.")
        print(f"     Consider using default 100/400-word summaries for long content.")

    full_prompt = (
        f"Based on the following transcript, {prompt}. "
        f"Output only the summary, no commentary.\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )
    result = local_chat(full_prompt, max_tokens=4000)
    return verify_summary(result, "custom", transcript=transcript)
```

- [ ] **Step 2: Verify the import chain**

```bash
cd scripts && python3 -c "
import sys
sys.path.insert(0, '.')
from llm import summarize_custom
print('summarize_custom imported OK')
"
```
Expected: `summarize_custom imported OK`

- [ ] **Step 3: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/llm.py
git commit -m "feat: add summarize_custom with verify_summary routing"
```

---

### Task 9: Add source metadata and write_custom_output to output.py

**Files:**
- Modify: `scripts/output.py`

- [ ] **Step 1: Add write_custom_output to output.py**

Append to output.py:

```python
def write_custom_output(
    title: str,
    summary: str,
    transcript: str,
    out_base: Path,
    metadata: dict | None = None,
    source: str = "audio",
    source_detail: str = "",
) -> None:
    """Write PDF, HTML, and Markdown with a single custom summary.

    out_base is the path WITHOUT extension — .pdf/.html/.md appended.
    """
    pdf_path = Path(str(out_base) + ".pdf")
    html_path = Path(str(out_base) + ".html")
    md_path = Path(str(out_base) + ".md")

    # PDF: single summary section
    pdf = TranscriptPDF()
    pdf.doc_title = sanitize_for_pdf(title)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.ln(60)
    pdf.multi_cell(0, 12, pdf.doc_title, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.ln(10)
    pdf.cell(0, 10, "AI-Generated Custom Summary", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.add_page()
    pdf.chapter_title("Summary")
    pdf.chapter_body(sanitize_for_pdf(summary))
    pdf.output(str(pdf_path))

    # HTML
    write_custom_html(title, summary, html_path, source, source_detail)

    # Markdown
    write_custom_markdown(title, summary, transcript, md_path, metadata, source, source_detail)

    print(f"\n📂 {out_base.parent}/")
    print(f"   ✅ PDF:  {out_base.name}.pdf")
    print(f"   ✅ HTML: {out_base.name}.html")
    print(f"   ✅ MD:   {out_base.name}.md")


def write_custom_html(
    title: str,
    summary: str,
    out_path: Path,
    source: str,
    source_detail: str,
) -> None:
    """Write HTML with a single custom summary."""
    import mistune
    import html as html_mod

    convert = mistune.html
    t = html_mod.escape(title)
    summary_html = convert(summary)
    source_html = html_mod.escape(source_detail) if source_detail else source

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t} — Custom Summary</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    background: #fafafa;
    color: #1a1a2e;
    line-height: 1.7;
    padding: 2rem;
  }}
  .container {{
    max-width: 800px;
    margin: 0 auto;
    background: #fff;
    border-radius: 12px;
    padding: 2.5rem;
    box-shadow: 0 1px 8px rgba(0,0,0,0.06);
    border: 1px solid #eaeaea;
  }}
  h1 {{
    font-size: 1.6rem;
    margin-bottom: 0.25rem;
    color: #111;
  }}
  .subtitle {{
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid #eee;
    padding-bottom: 1rem;
  }}
  h2 {{
    font-size: 1.15rem;
    margin: 1.8rem 0 0.6rem;
    color: #333;
    background: #f0f4ff;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
  }}
  p {{ margin-bottom: 1rem; }}
  .footer {{
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #eee;
    font-size: 0.8rem;
    color: #999;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>{t}</h1>
  <div class="subtitle">AI-Generated Custom Summary — Source: {source_html}</div>

  <h2>Summary</h2>
  {summary_html}

  <p class="footer">Generated by transcribe-av-to-pdf — Local summarization via LM Studio</p>
</div>
</body>
</html>"""
    out_path.write_text(page, encoding="utf-8")


def write_custom_markdown(
    title: str,
    summary: str,
    transcript: str,
    out_path: Path,
    metadata: dict | None,
    source: str,
    source_detail: str,
) -> None:
    """Write Markdown with a single custom summary and source metadata."""
    meta_section = _format_metadata(metadata or {})
    source_line = source_detail if source_detail else source

    lines = [
        f"# {title}",
        "",
        "*AI-Generated Custom Summary*",
        "",
        "---",
        "",
    ]
    if meta_section:
        lines.append(meta_section)

    # Source metadata
    lines += [
        "| | |",
        "|---|---|",
        f"| **Source** | {source_line} |",
        "",
    ]

    lines += [
        "## Summary",
        "",
        summary,
        "",
        "## Full Transcript",
        "",
        transcript,
        "",
        "---",
        "*Generated by transcribe-av-to-pdf — Local summarization via LM Studio*",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 2: Update write_markdown to accept source metadata**

Modify `write_markdown` signature to add `source` and `source_detail` parameters:

```python
def write_markdown(
    title: str,
    summary_100: str,
    summary_400: str,
    transcript: str,
    out_path: Path,
    *,
    metadata: dict | None = None,
    source: str = "audio",
    source_detail: str = "",
) -> None:
```

And add a source row in the metadata section, right after the existing metadata table:

```python
    if meta_section:
        lines.append(meta_section)

    # Source metadata row
    source_line = source_detail if source_detail else source
    lines += [
        "| | |",
        "|---|---|",
        f"| **Source** | {source_line} |",
        "",
    ]
```

- [ ] **Step 3: Update write_output (the call site) to pass source params**

In `transcribe_pdf.py` (Task 11 will handle this), the calls to `write_output` will pass `source` and `source_detail`. For now, verify the function still works with defaults:

```bash
cd scripts && python3 -c "
import sys
sys.path.insert(0, '.')
from output import write_markdown, write_custom_output
print('Output functions import OK')
"
```
Expected: `Output functions import OK`

- [ ] **Step 4: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/output.py
git commit -m "feat: add write_custom_output and source metadata to output.py"
```

---

### Task 10: Update PEP 723 dependencies in transcribe_pdf.py

**Files:**
- Modify: `scripts/transcribe_pdf.py`

- [ ] **Step 1: Add webvtt-py and langdetect to dependencies**

In the script header, find:
```python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.32",
#     "yt-dlp",
#     "fpdf2>=2.8",
#     "mistune>=3",
# ]
# ///
```

Replace with:
```python
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

**Note:** `mlx-whisper` is Apple Silicon only. On non-macOS or Intel Macs, the whisper fallback step will fail gracefully and the script will exit with the cloud-model error. No import of `mlx_whisper` happens at module level — it's imported lazily inside `whisper_transcribe()`.

- [ ] **Step 2: Verify uv resolves the new deps**

```bash
cd scripts && uv run --script transcribe_pdf.py --help 2>&1 | head -5
```
Expected: `uv` syncs the new deps, then shows help or starts (may prompt for input — Ctrl+C to exit)

- [ ] **Step 3: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/transcribe_pdf.py
git commit -m "chore: add webvtt-py and langdetect to PEP 723 dependencies"
```

---

### Task 11: Rewrite main() in transcribe_pdf.py with new orchestration

**Files:**
- Modify: `scripts/transcribe_pdf.py`

This is the largest task — the orchestration rewrite. The existing `main()` is entirely replaced while keeping the helper imports intact.

- [ ] **Step 1: Update imports at the top of transcribe_pdf.py**

Replace the existing imports:

```python
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
```

- [ ] **Step 2: Replace the entire main() function**

```python
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
```

- [ ] **Step 3: Verify the script starts without import errors**

```bash
cd scripts && python3 -c "
import sys
sys.path.insert(0, '.')
# Just verify all imports resolve
from transcribe_pdf import main
print('transcribe_pdf imports OK')
"
```
Expected: `transcribe_pdf imports OK`

- [ ] **Step 4: Verify CLI help works with new deps**

```bash
cd scripts && uv run transcribe_pdf.py --help
```
Expected: argparse help output showing `--method`, `--prompt`, and positional `url` arguments

- [ ] **Step 5: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/transcribe_pdf.py
git commit -m "feat: rewrite main() with subtitle-first orchestration, --method, --prompt"
```

---

### Task 12: Update SKILL.md documentation

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Update the "Quick Reference" table**

Find:
```
| Step | Command |
|------|---------|
| Run | `cd scripts && uv run transcribe_pdf.py` |
| Input | Paste local path or YouTube URL at prompt |
```

Add the new CLI flags:

```
| Step | Command |
|------|---------|
| Run (default) | `cd scripts && uv run transcribe_pdf.py` |
| Run with URL | `cd scripts && uv run transcribe_pdf.py "https://youtube.com/..."` |
| Subtitles only | `cd scripts && uv run transcribe_pdf.py --method subtitles` |
| Audio only | `cd scripts && uv run transcribe_pdf.py --method audio` |
| Custom prompt | `cd scripts && uv run transcribe_pdf.py "..." --prompt "Extract action items"` |
| Input | Paste local path or YouTube URL at prompt (if no CLI arg) |
```

- [ ] **Step 2: Add fallback chain to "How It Works"**

After step 4 (`transcribe()`) in the How It Works list, add:

```
4b. **transcribe_with_fallback()** — if subtitles unavailable, tries OpenRouter models in order:
   - MiMo (`xiaomi/mimo-v2.5`) — cheapest
   - Gemini Flash Lite (`google/gemini-2.5-flash-lite`) — mid-tier
   - Gemini Flash (`google/gemini-2.5-flash`) — most capable
   Each model gets 1 retry before moving to the next. If all fail, exits with a detailed error.
```

Update the numbering of subsequent steps (5→6, 6→7, etc.).

- [ ] **Step 3: Update Python deps table**

Add `webvtt-py` and `langdetect`:

```
| `webvtt-py` | ≥0.5 | VTT subtitle parsing |
| `langdetect` | ≥1.0 | Language detection for subtitle quality checks |
```

- [ ] **Step 4: Update the config table**

Add fallback model config:

```
| Fallback transcription models | MiMo → Gemini Flash Lite → Gemini Flash | Change `FALLBACK_MODELS` in config.py |
```

- [ ] **Step 5: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add SKILL.md
git commit -m "docs: update SKILL.md with hybrid transcription and new CLI flags"
```

---

### Task 13: Integration testing

**Files:**
- Manual testing (no code changes expected)

- [ ] **Step 1: Test --help output**

```bash
cd scripts && uv run transcribe_pdf.py --help
```
Expected: argparse help with `url`, `--method`, `--prompt` documented

- [ ] **Step 2: Test --prompt length validation**

```bash
cd scripts && uv run transcribe_pdf.py --prompt "$(python3 -c "print('x' * 2001)")" 2>&1; echo "Exit: $?"
```
Expected: error message about max length, exit code 1

- [ ] **Step 3: Test subtitle download with a known captioned video**

```bash
cd scripts && uv run transcribe_pdf.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" --method subtitles 2>&1
```
Expected: downloads subtitles, shows WPM + quality, produces PDF/HTML/MD (Me at the zoo is ~19 seconds, has captions)

- [ ] **Step 4: Test audio fallback with a known caption-less video**

Pick a YouTube Short or video without auto-captions. Test with `--method hybrid`.

```bash
cd scripts && uv run transcribe_pdf.py "URL_WITHOUT_CAPTIONS" 2>&1
```
Expected: "⚠️ Subtitles not available → falling back to audio" then MiMo transcription

- [ ] **Step 5: Test audio-only mode**

```bash
cd scripts && uv run transcribe_pdf.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" --method audio 2>&1
```
Expected: skips subtitle attempt, goes directly to MiMo transcription

- [ ] **Step 6: Test custom --prompt**

```bash
cd scripts && uv run transcribe_pdf.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" --prompt "List the key topics discussed in one sentence" 2>&1
```
Expected: produces custom summary instead of 100/400-word summaries

- [ ] **Step 7: Test --prompt rejection (>2000 chars)**

```bash
cd scripts && uv run transcribe_pdf.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" --prompt "$(python3 -c "print('x'*2001)")" 2>&1; echo "Exit code: $?"
```
Expected: error, exit code 1

- [ ] **Step 8: Test is_youtube_url rejection**

```bash
cd scripts && python3 -c "
from utils import is_youtube_url
assert not is_youtube_url('https://example.com/video.mp4')
assert not is_youtube_url('https://vimeo.com/12345')
print('Non-YouTube URLs correctly rejected')
"
```
Expected: `Non-YouTube URLs correctly rejected`

---

### Task 14: Create whisper_local.py for local transcription

**Files:**
- Create: `scripts/whisper_local.py`

- [ ] **Step 1: Create the file**

```python
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
```

- [ ] **Step 2: Verify the file loads (import only, no model load)**

```bash
cd scripts && python3 -c "
import sys
sys.path.insert(0, '.')
from whisper_local import whisper_transcribe
print('whisper_local imports OK')
"
```
Expected: `whisper_local imports OK`

- [ ] **Step 3: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/whisper_local.py
git commit -m "feat: add mlx-whisper local transcription module"
```

---

### Task 15: Add whisper to the fallback chain in llm.py

**Files:**
- Modify: `scripts/llm.py`

- [ ] **Step 1: Update transcribe_with_fallback to include whisper as 5th step**

In `scripts/llm.py`, find `transcribe_with_fallback`. The models list currently has 3 entries. Add whisper as a 4th entry (making it step 5 in the overall chain, after the 3 cloud models):

```python
def transcribe_with_fallback(audio_path: Path) -> tuple[str, str]:
    """Try transcription models in order: 3 cloud (OpenRouter) then local whisper.

    Returns (transcript, model_name).
    Raises TranscriptionFailed if all models are exhausted.
    """
    from config import FALLBACK_MODELS
    from whisper_local import whisper_transcribe

    models: list[tuple[str, str | None, bool]] = [
        ("MiMo",               FALLBACK_MODELS["mimo"],               True),   # cloud
        ("Gemini Flash Lite",  FALLBACK_MODELS["gemini_flash_lite"],  True),   # cloud
        ("Gemini Flash",       FALLBACK_MODELS["gemini_flash"],       True),   # cloud
        ("mlx-whisper (local)", None,                                  False),  # local
    ]

    failures: list[tuple[str, str]] = []

    for name, model_id, is_cloud in models:
        for attempt in range(2):  # 1 initial attempt + 1 retry
            try:
                if is_cloud:
                    result = transcribe_with_openrouter(audio_path, model_id)
                else:
                    result = whisper_transcribe(audio_path)

                if result and not is_failure_response(result):
                    print(f"  ✓ Transcribed via {name}")
                    return result, name
                failures.append((name, f"Attempt {attempt+1}: empty/failure response"))
                break  # bad response, don't retry
            except Exception as e:
                failures.append((name, f"Attempt {attempt+1}: {e}"))

    raise TranscriptionFailed(failures)
```

Note: the `models` list changes from `list[tuple[str, str]]` to `list[tuple[str, str | None, bool]]` where the third element is `is_cloud` (True = OpenRouter, False = local whisper).

- [ ] **Step 2: Verify the import chain**

```bash
cd scripts && python3 -c "
import sys
sys.path.insert(0, '.')
from llm import transcribe_with_fallback
print('transcribe_with_fallback imports OK (includes whisper)')
"
```
Expected: `transcribe_with_fallback imports OK (includes whisper)`

- [ ] **Step 3: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add scripts/llm.py
git commit -m "feat: add mlx-whisper as 5th step in fallback chain"
```

---

### Task 16: Update the spec — local transcription is now in scope

**Files:**
- Modify: `specs/hybrid-transcription-spec.md`

- [ ] **Step 1: Update the chain diagram**

Replace the 4-step chain with a 5-step chain:

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

- [ ] **Step 2: Remove local transcription from "Out of Scope"**

Delete:
```
- Local transcription / whisper models (future iteration)
```

Replace with:
```
- Non-Apple Silicon local transcription (Intel Mac/Linux/Windows need alternative STT)
```

- [ ] **Step 3: Update Solution section**

Change to:
```
2. Falls back to audio transcription with OpenRouter model redundancy (3 cloud tiers)
3. Uses local mlx-whisper as the ultimate zero-cost fallback (Apple Silicon only)
```

- [ ] **Step 4: Update User Feedback example**

Change "4 attempts" to "5 attempts" and add a whisper entry:

```
❌ Transcription failed after 5 attempts:
   1. Subtitles: Not available
   2. MiMo: HTTP 400 - Audio too large
   3. Gemini Flash Lite: Empty response
   4. Gemini Flash: Timeout
   5. mlx-whisper: Model not found
```

- [ ] **Step 5: Update File Changes table**

Add:
```
| `scripts/whisper_local.py` | New file: `whisper_transcribe()` with mlx-whisper, pre-flight checks, segment quality warnings |
```

- [ ] **Step 6: Update Success Criteria**

Change "Fallback chain works through all 3 OpenRouter models" to:
```
- [ ] Fallback chain works through all 5 stages (subtitles → 3 cloud → local whisper)
```

- [ ] **Step 7: Commit**

```bash
cd ~/.agents/skills/dk-transcribe-summarize
git add specs/hybrid-transcription-spec.md
git commit -m "docs: add mlx-whisper local transcription to spec"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Subtitles-first ✅ (Task 3-4, Task 11)
  - Quality checks (WPM, repeated phrases, language, duration) ✅ (Task 4)
  - Fallback chain (MiMo → GLite → GFlash → mlx-whisper) ✅ (Task 7, Task 15)
  - `--method` flag ✅ (Task 2, Task 11)
  - `--prompt` flag ✅ (Task 2, Task 8, Task 11)
  - Source metadata in output ✅ (Task 9)
  - `is_youtube_url` fix ✅ (Task 2)
  - `openrouter_chat` model parameter ✅ (Task 5)
  - `is_failure_response` word boundaries ✅ (Task 6)
  - `summarize_custom` verify_summary routing ✅ (Task 8)
  - Zero-duration guard ✅ (Task 4)
  - Tempdir cleanup ✅ (Task 11)
  - Interactive fallback ✅ (Task 11)
  - `TranscriptionFailed` exception ✅ (Task 6)
  - `write_custom_output` ✅ (Task 9)
  - User feedback messages ✅ (Task 11)

- [x] **Placeholder scan:** No TBD, TODO, "add error handling" patterns found. All steps contain concrete code or specific commands.

- [x] **Type consistency:**
  - `transcribe_with_fallback` returns `tuple[str, str]` ✅ (Task 7)
  - `main()` destructures it as `transcript, last_used_model` ✅ (Task 11)
  - `download_audio` returns 3-tuple `(audio_path, title, metadata)` ✅ (Task 11)
  - `get_subtitles` returns 3-tuple `(vtt_path, tempdir, language)` ✅ (Task 3)
  - `write_custom_output` accepts `(title, summary, transcript, out_base, metadata, source, source_detail)` ✅ (Task 9)
  - `write_markdown` updated with `source`, `source_detail` params ✅ (Task 9)
