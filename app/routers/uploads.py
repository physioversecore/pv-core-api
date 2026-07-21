import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from prisma import Prisma
from prisma.enums import Role

from app import get_current_user, get_db

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload"
REPORTS_ROOT = UPLOAD_ROOT / "Reports"
THERAPISTS_ROOT = UPLOAD_ROOT / "Therapists"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_REPORT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx"}
ALLOWED_THERAPIST_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx"}


def _sanitize_id(value: str) -> str:
    safe = Path(value).name
    if safe != value or ".." in value or "/" in value or "\\" in value:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    return safe


def _validate_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")
    return ext


def _validate_upload_size(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB")


@router.get("/{patient_id}/{filename}")
async def serve_file(
    patient_id: str,
    filename: str,
    current_user=Depends(get_current_user),
):
    patient_id = _sanitize_id(patient_id)
    file_path = (REPORTS_ROOT / patient_id / filename).resolve()

    if not str(file_path).startswith(str(REPORTS_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if current_user.role == Role.PATIENT and current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)


@router.get("/therapists/{therapist_id}/{filename}")
async def serve_therapist_file(
    therapist_id: str,
    filename: str,
    current_user=Depends(get_current_user),
):
    therapist_id = _sanitize_id(therapist_id)
    file_path = (THERAPISTS_ROOT / therapist_id / filename).resolve()

    if not str(file_path).startswith(str(THERAPISTS_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(str(file_path), media_type=media_type)


@router.post("/therapists/{therapist_id}")
async def upload_therapist_file(
    therapist_id: str,
    files: list[UploadFile] = File(...),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist_id = _sanitize_id(therapist_id)

    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    if current_user.role == Role.THERAPIST and therapist.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized")

    therapist_dir = THERAPISTS_ROOT / therapist_id
    therapist_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for f in files:
        ext = Path(f.filename or "file").suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = therapist_dir / filename

        content = await f.read()
        _validate_upload_size(content)
        _validate_filename(f.filename or "file")

        with open(dest, "wb") as out:
            out.write(content)

        original = f.filename or f"file{ext}"
        size = len(content)
        urls.append(f"/api/v1/uploads/therapists/{therapist_id}/{filename}?name={original}&size={size}")

    existing = [u.strip() for u in (therapist.mediaUrls or "").split(",") if u.strip()]
    all_urls = existing + urls
    await db.therapist.update(
        where={"id": therapist_id},
        data={"mediaUrls": ",".join(all_urls)},
    )

    return {"urls": urls, "total": len(all_urls)}
