"""Groq Vision OCR — extract text from scanned/image PDF pages.

Uses the Groq chat-completions API with a vision-capable model
(llama-4-scout) to OCR each page of a PDF that pdfplumber cannot read.

Flow:
  1. PyMuPDF (fitz) renders each PDF page as a PNG image
  2. Image is base64-encoded and sent to Groq vision model
  3. The model returns extracted text per page
  4. Results are assembled into LlamaIndex Document objects

This replaces the old Gemini-based OCR and avoids the need for
Tesseract or poppler system dependencies.
"""

import base64
import io
import logging
import time
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _render_pdf_pages_to_images(pdf_path: Path, *, dpi: int = 200) -> list[bytes]:
    """Render each page of a PDF to a PNG byte buffer using PyMuPDF.

    Returns a list of PNG byte strings, one per page.
    Skips pages that fail to render (logs a warning).
    """
    import fitz  # PyMuPDF

    images: list[bytes] = []
    doc = fitz.open(str(pdf_path))
    try:
        zoom = dpi / 72  # fitz default is 72 DPI
        matrix = fitz.Matrix(zoom, zoom)
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                pix = page.get_pixmap(matrix=matrix)
                images.append(pix.tobytes("png"))
            except Exception as e:
                logger.warning(
                    "PyMuPDF: failed to render page %d of '%s': %s",
                    page_num + 1, pdf_path.name, e,
                )
                images.append(b"")  # placeholder to keep page numbering aligned
    finally:
        doc.close()
    return images


def _ocr_image_with_groq(
    image_png: bytes,
    page_num: int,
    total_pages: int,
    file_name: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """Send a single page image to Groq vision and return extracted text."""
    from groq import Groq

    client = Groq(api_key=api_key or settings.GROQ_API_KEY)

    b64 = base64.b64encode(image_png).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64}"

    prompt = (
        f"This is page {page_num} of {total_pages} from an exam paper "
        f"'{file_name}'.\n\n"
        "Extract ALL visible text from this page with high accuracy.\n"
        "Preserve the original formatting: headings, numbered questions, "
        "sub-questions (a, b, c…), tables, and mathematical expressions.\n"
        "If a question has multiple parts, keep the part labels.\n"
        "Do NOT add commentary — only return the extracted text."
    )

    response = client.chat.completions.create(
        model=model or settings.GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        temperature=0.1,
        max_completion_tokens=4096,
    )

    return (response.choices[0].message.content or "").strip()


def load_pdf_with_groq_ocr(pdf_path: Path) -> list[Any]:
    """OCR an entire PDF via Groq vision, returning one LIDocument per page.

    This is the main entry-point called by the RAG engine when pdfplumber
    returns no text (scanned / image PDFs).

    Returns an empty list if:
      - GROQ_API_KEY is not configured
      - PyMuPDF or Groq SDK not installed
      - All pages fail OCR
    """
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — cannot use Groq vision OCR")
        return []

    from llama_index.core import Document as LIDocument

    t0 = time.time()
    logger.info("Groq Vision OCR: rendering pages of '%s'…", pdf_path.name)

    page_images = _render_pdf_pages_to_images(pdf_path)
    total_pages = len(page_images)

    if not page_images:
        logger.warning("PyMuPDF rendered 0 pages for '%s'", pdf_path.name)
        return []

    docs: list[LIDocument] = []
    chars_total = 0

    for i, img_bytes in enumerate(page_images, start=1):
        if not img_bytes:
            logger.debug("Skipping blank render for page %d", i)
            continue

        try:
            text = _ocr_image_with_groq(
                img_bytes, page_num=i, total_pages=total_pages,
                file_name=pdf_path.name,
            )
        except Exception as e:
            logger.warning(
                "Groq OCR failed on page %d of '%s': %s", i, pdf_path.name, e,
            )
            continue

        if not text:
            logger.debug("Groq returned empty text for page %d", i)
            continue

        chars_total += len(text)
        docs.append(LIDocument(
            text=text,
            metadata={
                "file_name": pdf_path.name,
                "file_path": str(pdf_path),
                "page_number": i,
                "total_pages": total_pages,
                "ocr_source": "groq_vision",
            },
        ))

    elapsed = round(time.time() - t0, 2)
    avg_chars = chars_total / len(docs) if docs else 0
    logger.info(
        "Groq Vision OCR: extracted %d page(s) from '%s' "
        "(avg %d chars/page, %.1fs)",
        len(docs), pdf_path.name, avg_chars, elapsed,
    )
    return docs
