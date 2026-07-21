import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from prisma import Prisma

from app import get_current_user, get_db

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "Upload"
REPORTS_ROOT = UPLOAD_ROOT / "Reports"
THERAPISTS_ROOT = UPLOAD_ROOT / "Therapists"


# ── serve report files (existing) ──


@router.get("/{patient_id}/{filename}")
async def serve_file(patient_id: str, filename: str):
    file_path = REPORTS_ROOT / patient_id / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    import mimetypes
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    return FileResponse(str(file_path), media_type=media_type)


# ── therapist media files ──


@router.get("/therapists/{therapist_id}/{filename}")
async def serve_therapist_file(therapist_id: str, filename: str):
    file_path = THERAPISTS_ROOT / therapist_id / filename
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
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    if current_user.role == "THERAPIST" and therapist.userId != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role not in ("THERAPIST", "ADMIN"):
        raise HTTPException(status_code=403, detail="Not authorized")

    therapist_dir = THERAPISTS_ROOT / therapist_id
    therapist_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for f in files:
        ext = Path(f.filename or "file").suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = therapist_dir / filename

        content = await f.read()
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
