"""Tests for wikinow.ingestion.

Verifies:
- Jina Reader parsing, auth header, error wrapping
- YouTube URL detection, json3 parsing, markdown formatting
- PDF/Epub error handling for missing deps and files
- Text file reading and title extraction from stem
- Audio English-only enforcement and format
- All response dataclasses are frozen

Usage:
    pytest tests/test_ingestion.py -v
"""

from unittest.mock import patch, MagicMock
from urllib.error import URLError

import pytest

from wikinow.ingestion.jina import JinaResponse, _parse_response
from wikinow.ingestion.youtube import (
    YouTubeResponse,
    format_as_markdown,
    is_youtube_url,
    _parse_json3,
)
from wikinow.ingestion.text import TextResponse, read as text_read
from wikinow.ingestion.audio import AudioResponse, format_as_markdown as format_audio
from wikinow.ingestion.pdf import PDFResponse
from wikinow.ingestion.epub import EpubResponse


# =============================================================================
# Jina Reader
# =============================================================================


class TestJinaReader:
    """Verify Jina Reader parsing, auth, and error wrapping."""

    def test_parse_response_extracts_title(self):
        title, content = _parse_response("# My Title\n\nSome content here.")
        assert title == "My Title"
        assert content == "Some content here."

    def test_parse_response_no_heading_uses_first_line(self):
        title, content = _parse_response("No heading here\nJust text")
        assert title == "No heading here"

    @patch("wikinow.ingestion.jina.urlopen")
    def test_fetch_builds_auth_header(self, mock_urlopen):
        from wikinow.ingestion.jina import fetch

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"# Test\n\nContent"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        fetch("https://example.com", api_key="my-secret-key")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer my-secret-key"

    @patch("wikinow.ingestion.jina.urlopen")
    def test_fetch_wraps_urlerror_as_connection_error(self, mock_urlopen):
        from wikinow.ingestion.jina import fetch

        mock_urlopen.side_effect = URLError("DNS lookup failed")

        with pytest.raises(ConnectionError, match="Failed to reach Jina Reader"):
            fetch("https://example.com")

    @patch("wikinow.ingestion.jina.urlopen")
    def test_fetch_wraps_httperror_as_connection_error(self, mock_urlopen):
        from urllib.error import HTTPError
        from wikinow.ingestion.jina import fetch

        mock_urlopen.side_effect = HTTPError(
            "https://r.jina.ai/test", 403, "Forbidden", {}, None
        )

        with pytest.raises(ConnectionError, match="Jina Reader returned 403"):
            fetch("https://example.com")


# =============================================================================
# YouTube — URL Detection
# =============================================================================


class TestYouTubeURLDetection:
    """Verify YouTube URL regex matching."""

    def test_is_youtube_url_watch(self):
        assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_is_youtube_url_short(self):
        assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ")

    def test_is_youtube_url_shorts(self):
        assert is_youtube_url("https://youtube.com/shorts/abc123")

    def test_is_youtube_url_rejects_non_youtube(self):
        assert not is_youtube_url("https://example.com/watch?v=abc")
        assert not is_youtube_url("https://vimeo.com/123456")


# =============================================================================
# YouTube — Fetch Error Handling
# =============================================================================


class TestYouTubeFetchErrors:
    """Verify YouTube fetch error paths."""

    def test_fetch_no_ytdlp_raises(self, monkeypatch):
        import wikinow.ingestion.youtube as yt_mod

        monkeypatch.setattr(yt_mod, "yt_dlp", None)
        with pytest.raises(ImportError, match="yt-dlp"):
            yt_mod.fetch("https://www.youtube.com/watch?v=test")

    def test_fetch_via_whisper_returns_empty_when_no_whisper(self, monkeypatch):
        import wikinow.ingestion.youtube as yt_mod

        # Mock _download_audio to return empty (no audio file found)
        monkeypatch.setattr(yt_mod, "_download_audio", lambda url, tmp: "")
        result = yt_mod._fetch_via_whisper("https://example.com", "/tmp/nonexistent")
        assert result == ""


# =============================================================================
# YouTube — json3 Parsing
# =============================================================================


class TestYouTubeJson3:
    """Verify json3 subtitle format parsing."""

    def test_parse_json3_extracts_text(self):
        data = {
            "events": [
                {"segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
                {"segs": [{"utf8": "Second line"}]},
            ]
        }
        result = _parse_json3(data)
        assert "Hello world" in result
        assert "Second line" in result

    def test_parse_json3_skips_empty_segs(self):
        data = {
            "events": [
                {"segs": [{"utf8": ""}]},
                {"segs": [{"utf8": "\n"}]},
                {"segs": [{"utf8": "Real content"}]},
            ]
        }
        result = _parse_json3(data)
        assert result == "Real content"


# =============================================================================
# YouTube — Formatting
# =============================================================================


class TestYouTubeFormat:
    """Verify YouTube markdown formatting."""

    def test_format_markdown_with_transcript(self):
        response = YouTubeResponse(
            title="Test Video",
            channel="Test Channel",
            description="A test description",
            transcript="Hello world this is a transcript",
            url="https://youtube.com/watch?v=test",
            duration=185,
        )
        md = format_as_markdown(response)
        assert "# Test Video" in md
        assert "**Channel:** Test Channel" in md
        assert "**Duration:** 3m 5s" in md
        assert "## Transcript" in md
        assert "Hello world" in md

    def test_format_markdown_handles_empty_transcript(self):
        response = YouTubeResponse(
            title="Test Video",
            channel="Test Channel",
            description="A test",
            transcript="",
            url="https://youtube.com/watch?v=test",
            duration=120,
        )
        md = format_as_markdown(response)
        assert "*No transcript available.*" in md

    def test_format_markdown_includes_description(self):
        response = YouTubeResponse(
            title="T",
            channel="C",
            description="My description here",
            transcript="text",
            url="u",
            duration=0,
        )
        md = format_as_markdown(response)
        assert "## Description" in md
        assert "My description here" in md

    def test_format_markdown_skips_empty_description(self):
        response = YouTubeResponse(
            title="T",
            channel="C",
            description="",
            transcript="text",
            url="u",
            duration=0,
        )
        md = format_as_markdown(response)
        assert "## Description" not in md


# =============================================================================
# PDF
# =============================================================================


class TestPDF:
    """Verify PDF extraction error handling."""

    def test_pdf_extract_no_pymupdf(self, monkeypatch):
        import wikinow.ingestion.pdf as pdf_mod

        monkeypatch.setattr(pdf_mod, "pymupdf", None)
        with pytest.raises(ImportError, match="pymupdf"):
            pdf_mod.extract("/tmp/any.pdf")

    def test_pdf_extract_missing_file(self):
        from wikinow.ingestion.pdf import extract

        with pytest.raises((FileNotFoundError, ImportError)):
            extract("/tmp/nonexistent-wikinow-test.pdf")

    def test_pdf_response_frozen(self):
        r = PDFResponse(title="T", content="C", pages=1, path="/tmp/t.pdf")
        with pytest.raises(AttributeError):
            r.title = "changed"


# =============================================================================
# Epub
# =============================================================================


class TestEpub:
    """Verify Epub extraction error handling."""

    def test_epub_extract_no_ebooklib(self, monkeypatch):
        import wikinow.ingestion.epub as epub_mod

        monkeypatch.setattr(epub_mod, "ebooklib", None)
        with pytest.raises(ImportError, match="ebooklib"):
            epub_mod.extract("/tmp/any.epub")

    def test_epub_extract_missing_file(self):
        from wikinow.ingestion.epub import extract

        with pytest.raises((FileNotFoundError, ImportError)):
            extract("/tmp/nonexistent-wikinow-test.epub")


# =============================================================================
# Text
# =============================================================================


class TestText:
    """Verify text file reading and title extraction."""

    def test_text_read_content(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# My Notes\n\nSome content here.", encoding="utf-8")
        result = text_read(f)
        assert isinstance(result, TextResponse)
        assert "My Notes" in result.content
        assert result.title == "Notes"

    def test_text_read_missing_file(self):
        with pytest.raises(FileNotFoundError, match="File not found"):
            text_read("/tmp/nonexistent-wikinow-test.md")

    def test_text_title_from_stem(self, tmp_path):
        f = tmp_path / "my-research_notes.md"
        f.write_text("content", encoding="utf-8")
        result = text_read(f)
        assert result.title == "My Research Notes"


# =============================================================================
# Audio
# =============================================================================


class TestAudio:
    """Verify audio transcription error handling and English-only enforcement."""

    def test_audio_transcribe_no_whisper(self, monkeypatch):
        import wikinow.ingestion.audio as audio_mod

        monkeypatch.setattr(audio_mod, "whisper", None)
        with pytest.raises(ImportError, match="openai-whisper"):
            audio_mod.transcribe("/tmp/any.mp3")

    def test_audio_transcribe_missing_file(self):
        from wikinow.ingestion.audio import transcribe

        with pytest.raises((ImportError, FileNotFoundError)):
            transcribe("/tmp/nonexistent-wikinow-test.mp3")

    def test_audio_non_english_raises(self, monkeypatch, tmp_path):
        import wikinow.ingestion.audio as audio_mod

        class FakeModel:
            def transcribe(self, path):
                return {"text": "Bonjour le monde", "language": "fr", "duration": 10.0}

        class FakeWhisper:
            @staticmethod
            def load_model(name):
                return FakeModel()

        monkeypatch.setattr(audio_mod, "whisper", FakeWhisper())
        fake = tmp_path / "french.mp3"
        fake.write_bytes(b"\x00" * 100)

        with pytest.raises(ValueError, match="Non-English audio detected"):
            audio_mod.transcribe(fake, model_name="turbo")

    def test_audio_english_succeeds(self, monkeypatch, tmp_path):
        import wikinow.ingestion.audio as audio_mod

        class FakeModel:
            def transcribe(self, path):
                return {"text": "Hello world", "language": "en", "duration": 5.0}

        class FakeWhisper:
            @staticmethod
            def load_model(name):
                return FakeModel()

        monkeypatch.setattr(audio_mod, "whisper", FakeWhisper())
        fake = tmp_path / "english.mp3"
        fake.write_bytes(b"\x00" * 100)

        result = audio_mod.transcribe(fake, model_name="turbo")
        assert isinstance(result, AudioResponse)
        assert result.language == "en"
        assert result.transcript == "Hello world"

    def test_audio_format_markdown(self):
        response = AudioResponse(
            title="My Podcast",
            transcript="Hello world this is a test",
            language="en",
            duration=125.5,
            path="/tmp/podcast.mp3",
        )
        md = format_audio(response)
        assert "# My Podcast" in md
        assert "**Language:** en" in md
        assert "**Duration:** 2m 5s" in md
        assert "Hello world" in md


# =============================================================================
# Frozen Dataclasses
# =============================================================================


class TestFrozenDataclasses:
    """Verify all response dataclasses are immutable."""

    def test_all_response_dataclasses_frozen(self):
        responses = [
            JinaResponse(title="T", content="C", url="U"),
            YouTubeResponse(
                title="T",
                channel="C",
                description="D",
                transcript="T",
                url="U",
                duration=0,
            ),
            PDFResponse(title="T", content="C", pages=1, path="P"),
            EpubResponse(title="T", author="A", content="C", chapters=1, path="P"),
            TextResponse(title="T", content="C", path="P"),
            AudioResponse(
                title="T", transcript="T", language="en", duration=0.0, path="P"
            ),
        ]
        for r in responses:
            with pytest.raises(AttributeError):
                r.title = "hacked"
