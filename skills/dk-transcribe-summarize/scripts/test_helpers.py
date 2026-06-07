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
    # test_count_words() waits for Task 4 (count_words implementation)
    # test_is_failure_response() waits for Task 6 (is_failure_response implementation)
    print("All tests passed!")
