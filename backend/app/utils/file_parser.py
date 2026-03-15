from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import pdfplumber
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


@lru_cache(maxsize=1)
def _get_paddle_ocr_engine():
    # PaddleX performs online model-source checks by default; disable for offline containers.
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang="ch")


@lru_cache(maxsize=1)
def _get_rapidocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


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


def _extract_doc_text(content: bytes) -> str:
    # Legacy .doc parsing is unreliable without external office tooling.
    return content.decode("utf-8", errors="ignore").strip()


@lru_cache(maxsize=1)
def _register_cjk_font() -> str:
    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"
    return font_name


def _text_to_pdf(content: str) -> bytes:
    text = content.strip() or "文档内容为空或暂不支持解析该格式。"
    buffer = BytesIO()
    page_width, page_height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    font_name = _register_cjk_font()
    font_size = 11
    line_height = 18
    left = 40
    top = page_height - 48
    bottom = 40
    max_chars = 46

    pdf.setFont(font_name, font_size)
    y = top
    lines: list[str] = []
    for block in text.splitlines() or [text]:
        block = block.strip()
        if not block:
            lines.append("")
            continue
        while len(block) > max_chars:
            lines.append(block[:max_chars])
            block = block[max_chars:]
        lines.append(block)

    for line in lines:
        if y < bottom:
            pdf.showPage()
            pdf.setFont(font_name, font_size)
            y = top
        pdf.drawString(left, y, line)
        y -= line_height

    pdf.save()
    return buffer.getvalue()


def _try_office_to_pdf(file_name: str, content: bytes) -> bytes | None:
    if shutil.which("soffice") is None:
        return None

    suffix = Path(file_name).suffix.lower()
    if suffix not in {".doc", ".docx"}:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / f"input{suffix}"
        input_path.write_bytes(content)

        try:
            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    temp_dir,
                    str(input_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return None

        output_path = input_path.with_suffix(".pdf")
        if output_path.exists():
            return output_path.read_bytes()
        return None


def convert_resume_to_preview_pdf(file_name: str, content: bytes) -> bytes:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        return content

    converted = _try_office_to_pdf(file_name, content)
    if converted is not None:
        return converted

    if suffix == ".docx":
        return _text_to_pdf(_extract_docx_text(content))

    if suffix == ".doc":
        return _text_to_pdf(_extract_doc_text(content))

    return _text_to_pdf(content.decode("utf-8", errors="ignore"))


def _extract_texts_from_paddle_result(result: Any) -> list[str]:
    if result is None:
        return []

    if isinstance(result, dict):
        texts = result.get("rec_texts") or result.get("texts") or []
        return [str(text).strip() for text in texts if str(text).strip()]

    if hasattr(result, "res"):
        return _extract_texts_from_paddle_result(result.res)

    if hasattr(result, "json"):
        return _extract_texts_from_paddle_result(result.json)

    if isinstance(result, (list, tuple)):
        text_lines: list[str] = []
        for item in result:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                candidate = item[1][0] if item[1] else None
                if candidate:
                    text_lines.append(str(candidate).strip())
                continue
            text_lines.extend(_extract_texts_from_paddle_result(item))
        return [line for line in text_lines if line]

    return []


def _extract_text_with_paddle(image_path: str) -> str:
    ocr = _get_paddle_ocr_engine()
    if hasattr(ocr, "predict"):
        result = ocr.predict(image_path)
    else:
        result = ocr.ocr(image_path, cls=True)
    return "\n".join(_extract_texts_from_paddle_result(result))


def _extract_text_with_rapidocr(image_path: str) -> str:
    ocr = _get_rapidocr_engine()
    result, _ = ocr(image_path)
    if not result:
        return ""

    text_lines: list[str] = []
    for item in result:
        if len(item) >= 2 and item[1]:
            text_lines.append(str(item[1]).strip())
    return "\n".join([line for line in text_lines if line])


def _extract_image_text(content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        errors: list[Exception] = []

        try:
            text = _extract_text_with_paddle(temp_file.name)
            if text.strip():
                return text
        except Exception as exc:
            errors.append(exc)

        try:
            text = _extract_text_with_rapidocr(temp_file.name)
            if text.strip():
                return text
        except Exception as exc:
            errors.append(exc)

    if errors:
        raise RuntimeError("image OCR failed") from errors[-1]
    return ""


def parse_resume_file(file_name: str, content: bytes) -> dict:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(content)
    elif suffix == ".docx":
        text = _extract_docx_text(content)
    elif suffix == ".doc":
        text = _extract_doc_text(content)
    elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        text = _extract_image_text(content)
    else:
        text = content.decode("utf-8", errors="ignore")

    return {"file_name": file_name, "size": len(content), "text": text}
