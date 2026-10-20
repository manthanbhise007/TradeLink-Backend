import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

from app.models import User
from app.security import require_seller

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def detect_image_type(data: bytes) -> str | None:
    """Identify the real image type from magic bytes (never trust the filename or Content-Type)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@router.post("", status_code=201)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    seller: User = Depends(require_seller),
):
    # Read at most MAX_BYTES + 1 so oversized files are rejected without loading them fully.
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 5 MB or smaller")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    ext = detect_image_type(data)
    if ext is None:
        raise HTTPException(status_code=415, detail="Only JPG, PNG, GIF or WebP images are allowed")

    filename = f"{secrets.token_hex(16)}.{ext}"  # random name: no path tricks, no collisions
    (UPLOAD_DIR / filename).write_bytes(data)

    # Absolute URL, because AuctionCreate.image_url is validated as HttpUrl.
    url = str(request.base_url).rstrip("/") + f"/uploads/files/{filename}"
    return {"url": url}