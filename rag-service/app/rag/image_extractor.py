"""PDF image extraction, captioning, and indexing for the RAG pipeline.

Extracts embedded images from PDF pages using PyMuPDF, generates captions
via the Groq Vision API, and stores them alongside text nodes so that
road signs, diagrams, charts, and other visual content can be retrieved
and displayed to students.

Storage layout::

    storage/{collection}/
        images/
            page_{N}_img_{M}.png     ← raw image file
        image_manifest.json          ← metadata: page, caption, path, dimensions

Flow during ingestion:
  1. PyMuPDF extracts all images from each PDF page
  2. Small/decorative images (<5 KB) are filtered out
  3. Remaining images are saved to disk under storage/{collection}/images/
  4. Groq Vision generates a caption/description for each image
  5. LlamaIndex Document nodes are created with the caption as text
     and image metadata (path, page, dimensions) attached
  6. These image nodes are indexed alongside text nodes

Flow during retrieval:
  - When a query matches an image node, the response includes
    image metadata (file path, caption) so the frontend can display it.
"""

import base64
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_images_from_pdf(pdf_path: Path, *, min_size_bytes: int = 5000) -> list[dict[str, Any]]:
    """Extract embedded images from a PDF using PyMuPDF.

    Returns a list of dicts with keys:
        - page_number (1-based)
        - image_bytes (raw PNG bytes)
        - width, height (pixels)
        - xref (PyMuPDF cross-reference id)
    """
    import fitz  # PyMuPDF

    images: list[dict[str, Any]] = []
    doc = fitz.open(str(pdf_path))

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            image_list = page.get_images(full=True)

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image["image"]

                    # Skip tiny/decorative images
                    if len(image_bytes) < min_size_bytes:
                        continue

                    # Convert to PNG if not already
                    img_ext = base_image.get("ext", "png")
                    if img_ext != "png":
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(io.BytesIO(image_bytes))
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            image_bytes = buf.getvalue()
                        except Exception:
                            pass  # Keep original format

                    images.append({
                        "page_number": page_idx + 1,
                        "image_index": img_idx,
                        "image_bytes": image_bytes,
                        "width": base_image.get("width", 0),
                        "height": base_image.get("height", 0),
                        "xref": xref,
                    })

                except Exception as e:
                    logger.debug(
                        "Failed to extract image xref=%d from page %d: %s",
                        xref, page_idx + 1, e,
                    )
    finally:
        doc.close()

    return images


def _render_page_region_with_images(
    pdf_path: Path, page_number: int, *, dpi: int = 200
) -> bytes:
    """Render a full PDF page to PNG for vision captioning.

    This is used as a fallback when extracted images lack context —
    the full page render includes labels, arrows, and surrounding text.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_number - 1]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    finally:
        doc.close()


def _caption_image_with_groq(
    image_png: bytes,
    *,
    page_number: int = 0,
    total_pages: int = 0,
    file_name: str = "",
    collection: str = "",
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """Generate a detailed caption for an image using Groq Vision."""
    from groq import Groq

    client = Groq(api_key=api_key or settings.GROQ_API_KEY)
    b64 = base64.b64encode(image_png).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64}"

    readable_collection = collection.replace("_", " ") if collection else ""
    context = f" from '{readable_collection}'" if readable_collection else ""

    prompt = (
        f"This image is from page {page_number} of {total_pages} of a document"
        f"{context} ('{file_name}').\n\n"
        "Describe this image in detail for an educational context:\n"
        "1. What type of image is it? (road sign, diagram, chart, map, illustration, photo, etc.)\n"
        "2. Describe ALL visible content: shapes, colors, symbols, text/labels, arrows\n"
        "3. What does it represent or mean?\n"
        "4. If it's a road sign: state the sign type (warning, regulatory, informational), "
        "its shape, colors, and what it indicates to drivers\n"
        "5. If it's a diagram: describe all components and their relationships\n\n"
        "Be thorough — students will search for this image by description. "
        "Include relevant keywords a student might use to find this image."
    )

    try:
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
            max_completion_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Groq Vision captioning failed: %s", e)
        return f"[Image from page {page_number} — caption unavailable]"


def extract_and_index_images(
    pdf_path: Path,
    collection: str,
    storage_dir: Path,
    *,
    min_size_bytes: int = 5000,
    max_images_per_page: int = 10,
    caption_images: bool = True,
) -> list[Any]:
    """Extract images from a PDF, caption them, and create indexable Document nodes.

    Args:
        pdf_path: Path to the PDF file
        collection: Collection name (e.g. 'DRIVING_Road_Signs_and_Markings')
        storage_dir: Root storage directory
        min_size_bytes: Minimum image size to consider (filters decorative images)
        max_images_per_page: Cap images per page to avoid runaway extraction
        caption_images: Whether to generate captions via Vision LLM

    Returns:
        List of LlamaIndex Document objects with image captions as text
        and image metadata attached.
    """
    from llama_index.core import Document as LIDocument

    t0 = time.time()

    # Create images directory
    images_dir = storage_dir / collection / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Extract images from PDF
    raw_images = _extract_images_from_pdf(pdf_path, min_size_bytes=min_size_bytes)
    logger.info(
        "Extracted %d images from '%s' (min_size=%d bytes)",
        len(raw_images), pdf_path.name, min_size_bytes,
    )

    if not raw_images:
        return []

    # Count total pages for context
    import fitz
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    # Group by page and cap per-page count
    from collections import defaultdict
    by_page: dict[int, list[dict]] = defaultdict(list)
    for img in raw_images:
        pg = img["page_number"]
        if len(by_page[pg]) < max_images_per_page:
            by_page[pg].append(img)

    docs: list[LIDocument] = []
    manifest: list[dict[str, Any]] = []

    for page_num in sorted(by_page.keys()):
        page_images = by_page[page_num]

        for img_info in page_images:
            img_bytes = img_info["image_bytes"]
            img_idx = img_info["image_index"]

            # Generate a stable filename using content hash
            content_hash = hashlib.md5(img_bytes).hexdigest()[:8]
            img_filename = f"page_{page_num}_img_{img_idx}_{content_hash}.png"
            img_path = images_dir / img_filename

            # Save image to disk
            img_path.write_bytes(img_bytes)

            # Generate caption via Vision LLM
            caption = ""
            if caption_images and settings.GROQ_API_KEY:
                caption = _caption_image_with_groq(
                    img_bytes,
                    page_number=page_num,
                    total_pages=total_pages,
                    file_name=pdf_path.name,
                    collection=collection,
                )
                # Rate limit: Groq free tier is limited
                time.sleep(0.5)
            else:
                caption = (
                    f"Image from page {page_num} of {pdf_path.name} "
                    f"(dimensions: {img_info['width']}x{img_info['height']})"
                )

            # Build the text node with rich metadata
            node_text = (
                f"[IMAGE: Page {page_num}]\n"
                f"Source: {pdf_path.name}, Page {page_num}\n"
                f"Description: {caption}\n"
                f"Dimensions: {img_info['width']}x{img_info['height']} pixels"
            )

            metadata = {
                "file_name": pdf_path.name,
                "file_path": str(pdf_path),
                "page_number": page_num,
                "total_pages": total_pages,
                "content_type": "image",
                "image_path": str(img_path),
                "image_filename": img_filename,
                "image_collection": collection,
                "image_width": img_info["width"],
                "image_height": img_info["height"],
                "image_caption": caption,
            }

            docs.append(LIDocument(text=node_text, metadata=metadata))

            manifest.append({
                "filename": img_filename,
                "page_number": page_num,
                "width": img_info["width"],
                "height": img_info["height"],
                "caption": caption,
                "source_pdf": pdf_path.name,
            })

    # Save manifest for reference
    manifest_path = storage_dir / collection / "image_manifest.json"
    existing_manifest = []
    if manifest_path.exists():
        try:
            existing_manifest = json.loads(manifest_path.read_text())
        except Exception:
            pass
    existing_manifest.extend(manifest)
    manifest_path.write_text(json.dumps(existing_manifest, indent=2))

    elapsed = round(time.time() - t0, 2)
    logger.info(
        "Image extraction complete for '%s' [%s]: %d images, %d captioned, %.1fs",
        pdf_path.name, collection, len(docs),
        sum(1 for d in docs if "[IMAGE:" in d.text and "caption unavailable" not in d.text),
        elapsed,
    )

    return docs
