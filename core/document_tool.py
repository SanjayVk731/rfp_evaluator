"""Document Tool: extracts clean text from an uploaded supplier PDF."""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_CHARS = 60_000      # keep prompts within typical context limits
MIN_USEFUL_CHARS = 200  # below this the PDF is probably scanned / empty

# Text in a proposal that tries to instruct the evaluator instead of informing the buyer.
INJECTION_RE = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)|disregard (the|all|your) (instructions|rules)"
    r"|you are now|system prompt|(give|assign|award) (this supplier|us|me) (full|maximum|10)"
    r"|as an ai( language model)?|score (this|us) (10|highest|maximum)",
    re.I,
)


class DocumentError(Exception):
    """Raised when a PDF cannot be read at all."""


@dataclass
class ExtractedDocument:
    file_name: str
    sha256: str
    page_count: int
    text: str
    char_count: int
    body_chars: int = 0
    warnings: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"-\n(?=[a-z])", "", text)        # re-join hyphenated line breaks
    text = re.sub(r"[ \t\u00a0]+", " ", text)        # collapse horizontal whitespace
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)           # collapse blank lines
    return text.strip()


def extract_text(file_bytes: bytes, file_name: str = "document.pdf") -> ExtractedDocument:
    """Extract and clean the text of every page. Raises DocumentError for unreadable files."""
    if not file_bytes:
        raise DocumentError(f"{file_name}: file is empty.")
    if not file_bytes[:1024].lstrip().startswith(b"%PDF"):
        raise DocumentError(f"{file_name}: not a valid PDF (missing %PDF header).")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # noqa: BLE001
                raise DocumentError(f"{file_name}: PDF is password protected.") from exc
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            pages.append(f"[Page {i}]\n{page_text}")
    except DocumentError:
        raise
    except (PdfReadError, Exception) as exc:  # noqa: BLE001
        raise DocumentError(f"{file_name}: could not be parsed ({exc}).") from exc

    warnings: list[str] = []
    text = _clean("\n\n".join(pages))
    body_chars = len(re.sub(r"\[Page \d+\]", "", text).strip())

    if body_chars < MIN_USEFUL_CHARS:
        warnings.append(
            f"{file_name}: only {body_chars} characters of text extracted - the PDF may be scanned or blank. "
            "All criteria will likely be scored as missing evidence."
        )
    for num, body in re.findall(r"\[Page (\d+)\]\n?(.*?)(?=\[Page \d+\]|\Z)", text, flags=re.S):
        m = INJECTION_RE.search(body)
        if m:
            warnings.append(f"{file_name}: page {num} contains text that looks like an instruction to the AI "
                            f"(\"{m.group(0)}\"). The evaluator is told to ignore it; review this proposal manually.")
    if len(text) > MAX_CHARS:
        warnings.append(f"{file_name}: text truncated from {len(text)} to {MAX_CHARS} characters for the LLM.")
        text = text[:MAX_CHARS]

    return ExtractedDocument(
        file_name=file_name,
        sha256=hashlib.sha256(file_bytes).hexdigest(),
        page_count=len(pages),
        text=text,
        char_count=len(text),
        body_chars=body_chars,
        warnings=warnings,
    )
