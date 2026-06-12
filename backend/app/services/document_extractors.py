from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class TextExtractionResult:
    text: str
    extractor: str


def extract_text(name: str, media_type: str | None, data: bytes) -> TextExtractionResult | None:
    normalized_media_type = (media_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(name).suffix.lower()
    if normalized_media_type == "application/pdf" or suffix == ".pdf":
        return extract_pdf_text(data)
    return None


def extract_pdf_text(data: bytes) -> TextExtractionResult:
    if not data:
        return TextExtractionResult(text="", extractor="pypdf")
    try:
        from pypdf import PdfReader
    except ImportError:
        return TextExtractionResult(text="", extractor="pypdf-unavailable")

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return TextExtractionResult(text="", extractor="pypdf")
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return TextExtractionResult(text="\n\n".join(pages), extractor="pypdf")
    except Exception:
        return TextExtractionResult(text="", extractor="pypdf")
