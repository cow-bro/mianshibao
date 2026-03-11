from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
import tempfile

import pdfplumber
from docx import Document


@lru_cache(maxsize=1)
def _get_ocr_engine():
    # PaddleX performs online model-source checks by default; disable for offline containers.
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang="ch")


def _extract_pdf_text(content: bytes) -> str:
    text_blocks: list[str] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_blocks.append(page_text.strip())

    if text_blocks:
        return "\n\n".join(text_blocks)

    # Fallback for scanned PDFs: render pages as images then OCR.
    try:
        import pypdfium2 as pdfium

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_pdf:
            temp_pdf.write(content)
            temp_pdf.flush()
            doc = pdfium.PdfDocument(temp_pdf.name)
            ocr_blocks: list[str] = []
            for page_index in range(len(doc)):
                page = doc[page_index]
                pil_image = page.render(scale=2).to_pil()
                image_buf = BytesIO()
                pil_image.save(image_buf, format="PNG")
                page_text = _extract_image_text(image_buf.getvalue())
                if page_text.strip():
                    ocr_blocks.append(page_text.strip())
            return "\n\n".join(ocr_blocks)
    except Exception:
        return ""


def _extract_docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_image_text(content: bytes) -> str:
    try:
        ocr = _get_ocr_engine()
    except Exception as exc:
        raise RuntimeError("PaddleOCR is not installed") from exc

    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        result = ocr.ocr(temp_file.name, cls=True)
    if not result:
        return ""

    text_lines: list[str] = []
    for group in result:
        for line in group:
            if len(line) >= 2 and line[1] and line[1][0]:
                text_lines.append(str(line[1][0]).strip())
    return "\n".join([line for line in text_lines if line])


def parse_resume_file(file_name: str, content: bytes) -> dict:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(content)
    elif suffix in {".docx", ".doc"}:
        text = _extract_docx_text(content)
    elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        text = _extract_image_text(content)
    else:
        text = content.decode("utf-8", errors="ignore")

    return {"file_name": file_name, "size": len(content), "text": text}
