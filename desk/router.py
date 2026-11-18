"""Decide which pipeline handles an upload. Plain rules by file type, never an LLM."""

from pathlib import Path

IMAGE = "image"
AUDIO = "audio"
VIDEO = "video"
DOCUMENT = "document"
LOGS = "logs"
UNKNOWN = "unknown"

_EXTENSIONS = {
    IMAGE: {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"},
    AUDIO: {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aiff", ".aif", ".webm"},
    VIDEO: {".mp4", ".mov", ".m4v", ".avi", ".mkv"},
    DOCUMENT: {".pdf", ".txt", ".md"},
    LOGS: {".csv", ".log"},
}


def kind_of(filename: str, content_type: str | None = None) -> str:
    """Classify an upload by extension first, then by its MIME type."""
    suffix = Path(filename or "").suffix.lower()
    for kind, suffixes in _EXTENSIONS.items():
        if suffix in suffixes:
            # Browser mic recordings arrive as .webm with an audio MIME type; video .webm says video/.
            if suffix == ".webm" and content_type and content_type.startswith("video/"):
                return VIDEO
            return kind
    if content_type:
        major = content_type.split("/", 1)[0]
        if major in (IMAGE, AUDIO, VIDEO):
            return major
        if content_type in ("application/pdf", "text/plain", "text/markdown"):
            return DOCUMENT
    return UNKNOWN
