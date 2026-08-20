"""Safe upload helpers used by ingestion, evaluation, and catalog endpoints."""
from pathlib import PurePath
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.config import settings


async def read_upload_limited(file: UploadFile, *, max_bytes: Optional[int] = None) -> bytes:
    """Read an upload with a hard byte limit instead of trusting Content-Length."""
    limit = max_bytes or settings.max_upload_size_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds the configured limit of {limit} bytes.",
        )
    return content


def safe_upload_filename(filename: Optional[str], default: str = "upload") -> str:
    """Return only a basename so client paths cannot influence server filesystem paths."""
    candidate = (filename or default).replace("\\", "/")
    return PurePath(candidate).name or default
