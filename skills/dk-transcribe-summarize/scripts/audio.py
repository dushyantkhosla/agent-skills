"""Audio download (YouTube) and compression utilities."""

import mimetypes
import subprocess
import tempfile
from pathlib import Path

import yt_dlp


def download_audio(url: str) -> tuple[Path, str, dict]:
    """Download best audio from YouTube, extract to m4a.

    Returns (audio_path, title, metadata) where metadata contains
    channel, upload_date, view_count, like_count, channel_follower_count,
    and categories from the YouTube info dict.
    """
    tempdir = Path(tempfile.mkdtemp(prefix="yt_audio_"))
    outtmpl = str(tempdir / "download.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "noplaylist": True,
        "quiet": True,
        "cookiesfrombrowser": ("brave",),
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Find the resulting m4a file
    candidates = list(tempdir.glob("*.m4a"))
    if not candidates:
        candidates = (
            list(tempdir.glob("*.mp3"))
            + list(tempdir.glob("*.wav"))
            + list(tempdir.glob("*.webm"))
            + list(tempdir.glob("*.opus"))
        )
    if not candidates:
        raise RuntimeError(f"yt-dlp did not produce an audio file in {tempdir}")

    audio_path = candidates[0]
    title = info.get("title", audio_path.stem) if info else audio_path.stem

    metadata: dict = {}
    if info:
        for key in (
            "channel", "upload_date", "view_count",
            "like_count", "channel_follower_count", "categories",
        ):
            if (val := info.get(key)) is not None:
                metadata[key] = val

    return audio_path, title, metadata


def compress_audio_for_api(path: Path) -> Path:
    """Re-encode audio to a small speech-optimized MP3 to fit API limits."""
    out_path = path.with_suffix(".compressed.mp3")
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-vn", "-ar", "16000", "-ac", "1",
        "-codec:a", "libmp3lame", "-b:a", "8k",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def audio_to_data_uri(path: Path) -> str:
    """Encode audio file as a base64 data URI for multimodal API calls."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        ext = path.suffix.lower()
        mime = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
        }.get(ext, "audio/mpeg")
    data = path.read_bytes()
    import base64
    b64 = base64.b64encode(data).decode()
    return f"data:{mime};base64,{b64}"


def get_video_duration(url: str) -> int:
    """Get video duration in seconds from yt-dlp without downloading.

    Returns 0 if duration can't be determined (handled by quality check).
    """
    ydl_opts = {
        "quiet": True,
        "cookiesfrombrowser": ("brave",),
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return 0
            return int(info.get("duration", 0))
    except Exception:
        return 0


def get_subtitles(url: str) -> tuple[Path | None, Path | None, str]:
    """Download auto-generated English subtitles via yt-dlp.

    Returns (vtt_path, tempdir, language) where:
    - vtt_path is the .en.vtt file (or None if unavailable)
    - tempdir is the download directory (caller must clean up)
    - language is the detected language code (or "")

    Uses a single download=True call to avoid double-fetching YouTube.
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
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
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
