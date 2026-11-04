"""CV text extraction (PDF / DOCX) with explicit unreadable-file handling."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
ALLOWED = {".pdf": "application/pdf",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


class ExtractionResult:
    def __init__(self, status: str, text: str = "", error: str | None = None):
        self.status, self.text, self.error = status, text, error


def sniff(filename: str, data: bytes) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" and data[:5] == b"%PDF-":
        return ".pdf"
    if ext == ".docx" and data[:2] == b"PK":
        return ".docx"
    return None


def extract(filename: str, data: bytes) -> ExtractionResult:
    if len(data) == 0:
        return ExtractionResult("unreadable", error="The file is empty.")
    if len(data) > MAX_BYTES:
        return ExtractionResult("unsupported", error="The file is larger than 8 MB.")
    kind = sniff(filename, data)
    if kind is None:
        return ExtractionResult("unsupported", error="Please upload a PDF or DOCX file.")
    try:
        if kind == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                return ExtractionResult("unreadable", error="The PDF is password-protected.")
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        else:
            import docx
            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
    except Exception as e:  # corrupt or malformed file
        return ExtractionResult("unreadable", error=f"The file could not be read ({type(e).__name__}).")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 40:
        return ExtractionResult("unreadable", text=text,
                                error="Little or no text could be read (it may be a scanned image). "
                                      "Please upload a text-based PDF or DOCX, or enter details manually.")
    return ExtractionResult("ok", text=text[:60000])


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_URL = re.compile(r"https?://\S+")


def redact(text: str, names: list[str]) -> str:
    """Remove direct identifiers before assessment (blinding / data minimisation)."""
    out = _EMAIL.sub("[email]", text)
    out = _PHONE.sub("[phone]", out)
    out = _URL.sub("[link]", out)
    for name in names:
        for part in {name, *name.split()}:
            if len(part) >= 3:
                out = re.sub(re.escape(part), "[candidate]", out, flags=re.IGNORECASE)
    # Drop lines that commonly carry personal characteristics unrelated to the scorecard.
    out = re.sub(r"(?im)^\s*(date of birth|dob|age|gender|sex|marital status|nationality|religion|photo)\b.*$",
                 "[removed: personal characteristic not assessed]", out)
    return out
