"""Image serving routes — serve extracted PDF images for frontend display.

Routes:
  GET /images/{collection}/{filename}  → serve a specific extracted image
  GET /images/{collection}             → list all images in a collection
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_storage = Path(settings.STORAGE_DIR)


@router.get("/{collection}/{filename}")
async def serve_image(collection: str, filename: str):
    """Serve an extracted image file from a collection."""
    image_path = _storage / collection / "images" / filename

    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image '{filename}' not found in collection '{collection}'",
        )

    # Security: ensure the path doesn't escape the storage directory
    try:
        image_path.resolve().relative_to(_storage.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return FileResponse(
        path=str(image_path),
        media_type="image/png",
        filename=filename,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{collection}")
async def list_collection_images(collection: str):
    """List all extracted images and their metadata for a collection."""
    manifest_path = _storage / collection / "image_manifest.json"
    images_dir = _storage / collection / "images"

    if not images_dir.exists():
        return {"collection": collection, "images": [], "total": 0}

    # Load manifest if available
    manifest = []
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            pass

    # If no manifest, just list the image files
    if not manifest:
        image_files = sorted(images_dir.glob("*.png"))
        manifest = [
            {
                "filename": f.name,
                "page_number": _extract_page_from_filename(f.name),
                "caption": "",
                "source_pdf": "",
            }
            for f in image_files
        ]

    return {
        "collection": collection,
        "images": manifest,
        "total": len(manifest),
    }


def _extract_page_from_filename(filename: str) -> int:
    """Extract page number from filename like 'page_3_img_0_abc123.png'."""
    try:
        parts = filename.split("_")
        if parts[0] == "page":
            return int(parts[1])
    except (IndexError, ValueError):
        pass
    return 0
