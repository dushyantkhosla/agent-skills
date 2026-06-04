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
