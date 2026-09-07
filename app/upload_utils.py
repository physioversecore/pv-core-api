import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024

EXTENSION_TO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

INLINE_SAFE_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
}

_MAGIC_CHECKS: dict[str, bytes] = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".gif": b"GIF87a",
    ".pdf": b"%PDF-",
    ".doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    ".docx": b"PK\x03\x04",
}

_GIF89_PREFIX = b"GIF89a"


def check_magic_bytes(filename: str, content: bytes) -> bool:
    ext = Path(filename).suffix.lower()
    if not content:
        return False

    if ext in (".jpg", ".jpeg"):
        return content[:3] == _MAGIC_CHECKS[".jpg"]

    if ext == ".png":
        return content[:8] == _MAGIC_CHECKS[".png"]

    if ext == ".gif":
        return content[:6] in (b"GIF87a", _GIF89_PREFIX)

    if ext == ".webp":
        return b"RIFF" in content[:16] and content[8:12] == b"WEBP"

    if ext == ".pdf":
        return content[:5] == _MAGIC_CHECKS[".pdf"]

    if ext == ".docx":
        return content[:4] == b"PK\x03\x04"

    if ext == ".doc":
        if content[:8] == _MAGIC_CHECKS[".doc"]:
            return True
        return content[:4] == b"PK\x03\x04"

    return False


def validate_upload_file(filename: str, content: bytes) -> tuple[str, bytes]:
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSION_TO_MIME:
        raise HTTPException(status_code=400, detail="File type not allowed")

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    if not check_magic_bytes(filename, content):
        raise HTTPException(status_code=400, detail="File content does not match its type")

    return ext, content


def _sanitize_filename(name: str) -> str:
    clean = name.replace('"', "").replace("'", "").replace("\n", "").replace("\r", "")
    return "".join(c for c in clean if c.isalnum() or c in "._- ")


def serve_upload_response(file_path: Path, filename_display: str) -> FileResponse:
    ext = file_path.suffix.lower()
    media_type = EXTENSION_TO_MIME.get(ext, "application/octet-stream")
    headers: dict[str, str] = {"X-Content-Type-Options": "nosniff"}

    if ext not in INLINE_SAFE_EXTENSIONS:
        media_type = "application/octet-stream"
        headers["Content-Disposition"] = (
            f'attachment; filename="{_sanitize_filename(filename_display)}"'
        )

    return FileResponse(str(file_path), media_type=media_type, headers=headers)


def write_upload_file(dest: Path, content: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
    except Exception:
        os.close(fd)
        raise
