"""YouTube client — extract transcript via yt-dlp subtitles + Whisper fallback."""

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


_YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)"
)


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class YouTubeResponse:
    """Response from YouTube extraction."""

    title: str
    channel: str
    description: str
    transcript: str
    url: str
    duration: int


# ── Client ────────────────────────────────────────────────────────────────


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube video."""
    return bool(_YOUTUBE_RE.search(url))


def fetch(url: str) -> YouTubeResponse:
    """Extract transcript from YouTube. Tries subtitles first, then Whisper."""
    if yt_dlp is None:
        raise ImportError("yt-dlp is required: pip install wikinow[youtube]")

    with tempfile.TemporaryDirectory() as tmp:
        info, transcript = _fetch_subtitles(url, tmp)

        if not transcript:
            transcript = _fetch_via_whisper(url, tmp)

    return YouTubeResponse(
        title=info.get("title", ""),
        channel=info.get("channel", "") or info.get("uploader", ""),
        description=info.get("description", ""),
        transcript=transcript,
        url=url,
        duration=info.get("duration", 0) or 0,
    )


# ── Subtitles ─────────────────────────────────────────────────────────────


def _fetch_subtitles(url: str, tmp: str) -> tuple[dict, str]:
    """Try to get English subtitles via yt-dlp."""
    opts = {
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "json3",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(Path(tmp) / "%(id)s"),
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise ConnectionError(f"Failed to fetch YouTube video: {e}") from e

    sub_files = sorted(Path(tmp).glob("*.json3"))
    if not sub_files:
        return info, ""

    try:
        data = json.loads(sub_files[0].read_text(encoding="utf-8"))
        return info, _parse_json3(data)
    except (json.JSONDecodeError, KeyError):
        return info, ""


def _parse_json3(data: dict) -> str:
    """Parse json3 subtitle format into plain text."""
    lines = []
    for event in data.get("events", []):
        segs = event.get("segs", [])
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if text and text != "\n":
            lines.append(text)
    return "\n".join(lines)


# ── Whisper Fallback ──────────────────────────────────────────────────────


def _fetch_via_whisper(url: str, tmp: str) -> str:
    """Download audio and transcribe via Whisper. Returns empty if Whisper not installed."""
    try:
        from wikinow.ingestion.audio import transcribe
    except ImportError:
        return ""

    audio_path = _download_audio(url, tmp)
    if not audio_path:
        return ""

    try:
        result = transcribe(audio_path)
        return result.transcript
    except Exception:
        # ValueError = non-English, other errors = transcription failure
        return ""


def _download_audio(url: str, tmp: str) -> str:
    """Download audio only via yt-dlp."""
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(tmp) / "audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError:
        return ""

    audio_files = list(Path(tmp).glob("audio.*"))
    return str(audio_files[0]) if audio_files else ""


# ── Formatter ─────────────────────────────────────────────────────────────


def format_as_markdown(response: YouTubeResponse) -> str:
    """Format YouTube data as markdown for saving to raw/."""
    parts = [
        f"# {response.title}",
        "",
        f"**Channel:** {response.channel}",
        f"**URL:** {response.url}",
        f"**Duration:** {response.duration // 60}m {response.duration % 60}s",
        "",
    ]

    if response.description:
        parts.extend(["## Description", "", response.description, ""])

    if response.transcript:
        parts.extend(["## Transcript", "", response.transcript])
    else:
        parts.append("*No transcript available.*")

    return "\n".join(parts)
