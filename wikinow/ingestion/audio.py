"""Audio client — transcribe audio/video files via Whisper (local)."""

from dataclasses import dataclass
from pathlib import Path

try:
    import whisper
except ImportError:
    whisper = None


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AudioResponse:
    """Response from audio transcription."""

    title: str
    transcript: str
    language: str
    duration: float
    path: str


# ── Client ────────────────────────────────────────────────────────────────


def transcribe(file_path: str | Path, model_name: str = "") -> AudioResponse:
    """Transcribe an audio/video file using Whisper locally. Requires ffmpeg."""
    if whisper is None:
        raise ImportError("openai-whisper is required: pip install wikinow[whisper]")

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    if not model_name:
        from wikinow.config import get_whisper_config

        model_name = get_whisper_config().model

    model = whisper.load_model(model_name)
    result = model.transcribe(str(file_path))

    language = result.get("language", "")
    if language and language != "en":
        raise ValueError(
            f"Non-English audio detected (language: {language}). "
            f"WikiNow only supports English content."
        )

    return AudioResponse(
        title=file_path.stem.replace("-", " ").replace("_", " ").title(),
        transcript=result.get("text", ""),
        language=result.get("language", ""),
        duration=result.get("duration", 0.0) or 0.0,
        path=str(file_path),
    )


# ── Formatter ─────────────────────────────────────────────────────────────


def format_as_markdown(response: AudioResponse) -> str:
    """Format audio transcription as markdown for saving to raw/."""
    parts = [
        f"# {response.title}",
        "",
        f"**Language:** {response.language}",
        f"**Duration:** {int(response.duration) // 60}m {int(response.duration) % 60}s",
        f"**Source:** {response.path}",
        "",
        "## Transcript",
        "",
        response.transcript,
    ]

    return "\n".join(parts)
