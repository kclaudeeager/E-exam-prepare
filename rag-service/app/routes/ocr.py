"""Handwritten answer OCR endpoint — uses Groq Vision (VLM)."""

import base64
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class OCRRequest(BaseModel):
    """Handwritten answer OCR request."""

    image_base64: str  # Base64-encoded image (JPEG/PNG)
    prompt: str | None = None


class OCRResponse(BaseModel):
    """OCR result."""

    text: str
    success: bool = True


@router.post("/handwritten", response_model=OCRResponse)
async def ocr_handwritten(body: OCRRequest):
    """Transcribe a handwritten answer image using Groq Vision."""
    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GROQ_API_KEY not configured — OCR unavailable",
        )

    try:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)

        # Determine image MIME type from base64 header or default to JPEG
        image_data = body.image_base64
        mime_type = "image/jpeg"
        if image_data.startswith("data:"):
            # Extract MIME from data URI: data:image/png;base64,...
            header, image_data = image_data.split(",", 1)
            if "png" in header:
                mime_type = "image/png"
            elif "webp" in header:
                mime_type = "image/webp"

        prompt = body.prompt or (
            "Transcribe this handwritten text as accurately as possible. "
            "Preserve mathematical notation. If parts are unclear, indicate with [unclear]."
        )

        response = client.chat.completions.create(
            model=settings.GROQ_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=2000,
            temperature=0.1,
        )

        text = response.choices[0].message.content or ""
        logger.info("OCR transcribed %d chars from handwritten answer", len(text))
        return OCRResponse(text=text.strip(), success=True)

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="groq package not installed",
        )
    except Exception as e:
        logger.error("Handwritten OCR failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"OCR failed: {str(e)}",
        )
