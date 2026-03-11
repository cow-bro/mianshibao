"""Text chunking, Chinese tokenization, and document text extraction utilities."""

from __future__ import annotations

import io
import re

import jieba


def segment_chinese(text: str) -> str:
    """Segment Chinese text into space-separated tokens using jieba.

    Mixed Chinese/English text is handled gracefully: Chinese characters are
    segmented into words while English words are preserved as-is.
    """
    if not text or not text.strip():
        return ""
    tokens = jieba.lcut(text)
    return " ".join(t for t in tokens if t.strip())


# ── Document text extraction ──────────────────────────────


def extract_text_from_file(filename: str, content: bytes) -> str:
    """Extract plain text from a PDF, TXT, or Markdown file."""
    suffix = _suffix(filename)

    if suffix in (".txt", ".md", ".markdown"):
        return _decode_text(content)

    if suffix == ".pdf":
        return _extract_pdf_text(content)

    raise ValueError(f"Unsupported file type for knowledge ingestion: {suffix}")


def _suffix(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _decode_text(content: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", errors="replace")


def _extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text)


# ── Markdown section splitter ─────────────────────────────


def split_markdown_sections(text: str) -> list[dict]:
    """Split Markdown by headers into ``[{"title": ..., "content": ...}]``.

    Each ``#``, ``##``, or ``###`` header starts a new section.
    Content before the first header (if any) is captured with an empty title.
    """
    lines = text.split("\n")
    sections: list[dict] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        header_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if header_match:
            # Flush previous section
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({"title": current_title, "content": body})
            current_title = header_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    body = "\n".join(current_lines).strip()
    if body:
        sections.append({"title": current_title, "content": body})

    return sections


# ── Recursive text splitter ───────────────────────────────


class RecursiveTextSplitter:
    """Recursively split text using a hierarchy of separators.

    Designed for Chinese + English mixed content.  Splits at the coarsest
    separator first, then progressively finer ones for oversized pieces.
    Character-level splitting with overlap is used as a last resort.
    """

    DEFAULT_SEPARATORS = [
        "\n\n",  # Paragraph breaks
        "\n",    # Line breaks
        "。",    # Chinese period
        "！",    # Chinese exclamation
        "？",    # Chinese question mark
        "；",    # Chinese semicolon
        ".",     # English period
        "!",     # English exclamation
        "?",     # English question mark
        ";",     # English semicolon
        " ",     # Space
        "",      # Character-level (last resort)
    ]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))
        self.separators = separators or self.DEFAULT_SEPARATORS

    def split_text(self, text: str) -> list[str]:
        """Split *text* into chunks, each roughly ``chunk_size`` characters."""
        if not text or not text.strip():
            return []
        return self._split_recursive(text.strip(), list(self.separators))

    # ── internals ──────────────────────────────────────────

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        if not separators:
            return self._character_split(text)

        sep = separators[0]
        rest = separators[1:]

        if sep == "":
            return self._character_split(text)

        if sep not in text:
            return self._split_recursive(text, rest)

        parts = text.split(sep)
        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = (current + sep + part) if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                if len(part) > self.chunk_size:
                    chunks.extend(self._split_recursive(part, rest))
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def _character_split(self, text: str) -> list[str]:
        """Hard split by characters with built-in overlap."""
        step = max(1, self.chunk_size - self.chunk_overlap)
        chunks: list[str] = []
        for i in range(0, len(text), step):
            chunk = text[i : i + self.chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks
